# Database-Stored Instruments Plan

## Executive Summary

This document outlines a plan to store PyBirch instrument definitions in the database, enabling:
- **Browser-based instrument creation** - Create and edit instruments through the web UI
- **Per-computer instrument tracking** - Instruments remember their last adapter and computer
- **Automatic discovery** - PyBirch instances see instruments configured for their computer
- **Version control** - Track instrument code changes over time
- **Shared libraries** - Labs can share instrument implementations across computers

## Current Architecture Analysis

### How Instruments Work Today

```
┌─────────────────────────────────────────────────────────────────┐
│                    Python File System                           │
│  pybirch/Instruments/                                           │
│  ├── base.py          (Base classes)                            │
│  ├── AMETEK/          (Manufacturer-specific instruments)       │
│  ├── ESP/             (Motion controllers)                      │
│  ├── Generic/         (Generic backends)                        │
│  └── ...                                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ Dynamic import via get_classes_from_directory()
┌─────────────────────────────────────────────────────────────────┐
│                    PyBirch Runtime                              │
│  InstrumentSelectorWidget scans directories for Python classes  │
│  Classes must inherit from Movement/Measurement base classes    │
│  Adapters (VISA addresses) assigned at runtime                  │
└─────────────────────────────────────────────────────────────────┘
```

### Current Database Instrument Model

The existing `Instrument` model stores **metadata only**, not executable code:

```python
class Instrument(Base):
    id: int
    lab_id: int                    # Which lab owns this
    name: str                      # Display name
    instrument_type: str           # 'movement', 'measurement', 'fabrication'
    pybirch_class: str            # Class name reference (e.g., 'Keithley2400')
    manufacturer: str
    model: str
    serial_number: str
    adapter: str                   # VISA address (e.g., 'GPIB::8::INSTR')
    location: str
    status: str                    # 'available', 'in_use', 'maintenance'
    specifications: dict           # JSON - technical specs
    extra_data: dict              # JSON - additional metadata
```

### Gap Analysis

| Current State | Desired State |
|---------------|---------------|
| Code in Python files on each computer | Code stored in database, synced to computers |
| `pybirch_class` is just a string | `pybirch_class` links to executable code |
| No computer tracking | Instruments track which computer they run on |
| Manual setup per computer | Auto-discovery from database |
| No version history | Full code versioning |

---

## Proposed Architecture

### New Database Schema

#### 1. InstrumentDefinition (New Table)

Stores the actual Python code for instruments:

```python
class InstrumentDefinition(Base):
    """
    Stores executable Python code for PyBirch instruments.
    This is the 'class definition' - reusable across multiple physical instruments.
    """
    __tablename__ = "instrument_definitions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Classification
    instrument_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'movement' or 'measurement'
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 'Lock-in Amplifier', 'Stage', etc.
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # The actual code
    source_code: Mapped[str] = mapped_column(Text, nullable=False)  # Full Python class definition
    base_class: Mapped[str] = mapped_column(String(100), nullable=False)  # 'FakeMeasurementInstrument', 'VisaBaseMovementInstrument', etc.
    dependencies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ['pyvisa', 'numpy', ...]
    
    # Configuration schema
    settings_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # JSON Schema for settings
    default_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Metadata for measurement instruments
    data_columns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ['X', 'Y', 'R']
    data_units: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)    # ['V', 'V', 'V']
    
    # Metadata for movement instruments
    position_column: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    position_units: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Ownership and versioning
    lab_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('labs.id'), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # Shared across labs?
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)  # Shipped with PyBirch?
    
    # Audit
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    lab: Mapped[Optional["Lab"]] = relationship("Lab")
    versions: Mapped[List["InstrumentDefinitionVersion"]] = relationship(back_populates="definition")
    instances: Mapped[List["Instrument"]] = relationship(back_populates="definition")
```

#### 2. InstrumentDefinitionVersion (New Table)

Version history for instrument code:

```python
class InstrumentDefinitionVersion(Base):
    """
    Version history for instrument definitions.
    Allows rollback and audit trail.
    """
    __tablename__ = "instrument_definition_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    definition_id: Mapped[int] = mapped_column(Integer, ForeignKey('instrument_definitions.id'))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    definition: Mapped["InstrumentDefinition"] = relationship(back_populates="versions")
```

#### 3. ComputerBinding (New Table)

Track which instruments belong to which computers:

```python
class ComputerBinding(Base):
    """
    Binds instrument instances to specific computers.
    Enables auto-discovery of instruments per PyBirch instance.
    """
    __tablename__ = "computer_bindings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey('instruments.id'))
    
    # Computer identification
    computer_name: Mapped[str] = mapped_column(String(255), nullable=False)  # hostname
    computer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # MAC address or UUID
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # OS username
    
    # Connection info (last known)
    adapter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # VISA address
    adapter_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'GPIB', 'USB', 'Serial', 'TCP'
    
    # Status
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)  # Primary computer for this instrument
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    instrument: Mapped["Instrument"] = relationship(back_populates="computer_bindings")
    
    __table_args__ = (
        UniqueConstraint('instrument_id', 'computer_name', name='uq_instrument_computer'),
    )
```

#### 4. Updated Instrument Model

Link to definition and track computer:

```python
class Instrument(Base):
    # ... existing fields ...
    
    # NEW: Link to definition
    definition_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('instrument_definitions.id'), nullable=True
    )
    
    # Relationships
    definition: Mapped[Optional["InstrumentDefinition"]] = relationship(back_populates="instances")
    computer_bindings: Mapped[List["ComputerBinding"]] = relationship(back_populates="instrument")
```

---

## Implementation Plan

### Phase 1: Database Schema & Migration (Week 1)

#### Tasks

1. **Create new models** in `database/models.py`
   - `InstrumentDefinition`
   - `InstrumentDefinitionVersion`
   - `ComputerBinding`
   - Update `Instrument` with `definition_id`

2. **Generate Alembic migration**
   ```bash
   alembic revision --autogenerate -m "Add instrument definitions and computer bindings"
   alembic upgrade head
   ```

3. **Update DatabaseService** with CRUD operations
   - `create_instrument_definition()`
   - `get_instrument_definitions(lab_id=None, type=None)`
   - `update_instrument_definition()` (creates version)
   - `get_instruments_for_computer(computer_name)`
   - `bind_instrument_to_computer()`

#### Deliverables
- [ ] New SQLAlchemy models
- [ ] Alembic migration script
- [ ] DatabaseService methods
- [ ] Unit tests for new operations

---

### Phase 2: Code Migration Tool (Week 1-2)

#### Tasks

1. **Create migration script** to extract existing instruments from Python files:

   ```python
   # scripts/migrate_instruments_to_database.py
   
   def extract_instrument_definition(cls):
       """Extract definition from a Python class."""
       import inspect
       
       source = inspect.getsource(cls)
       
       return {
           'name': cls.__name__,
           'display_name': getattr(cls, 'name', cls.__name__),
           'instrument_type': 'measurement' if hasattr(cls, 'perform_measurement') else 'movement',
           'source_code': source,
           'base_class': cls.__bases__[0].__name__,
           'data_columns': getattr(cls, 'data_columns', None),
           'data_units': getattr(cls, 'data_units', None),
           'position_units': getattr(cls, 'position_units', None),
       }
   ```

2. **Scan existing instruments** in `pybirch/Instruments/`

3. **Insert into database** with `is_builtin=True`

#### Deliverables
- [ ] Migration script
- [ ] All existing instruments in database
- [ ] Validation report

---

### Phase 3: Dynamic Class Loading (Week 2)

#### Tasks

1. **Create InstrumentFactory** class:

   ```python
   # pybirch/Instruments/factory.py
   
   class InstrumentFactory:
       """Factory for creating instrument instances from database definitions."""
       
       _class_cache: Dict[int, type] = {}
       
       @classmethod
       def create_class_from_definition(cls, definition: dict) -> type:
           """
           Dynamically create a Python class from database definition.
           
           Args:
               definition: InstrumentDefinition record as dict
               
           Returns:
               The dynamically created instrument class
           """
           if definition['id'] in cls._class_cache:
               return cls._class_cache[definition['id']]
           
           # Get base class
           base_class = cls._get_base_class(definition['base_class'])
           
           # Compile the source code
           namespace = {
               'np': numpy,
               'numpy': numpy,
               'pd': pandas,
               'pandas': pandas,
               # ... other common imports
           }
           namespace.update(cls._get_base_classes())
           
           exec(definition['source_code'], namespace)
           
           # Find the class in the namespace
           instrument_class = namespace[definition['name']]
           
           # Cache it
           cls._class_cache[definition['id']] = instrument_class
           
           return instrument_class
       
       @classmethod
       def create_instance(cls, definition: dict, adapter: str = '', **kwargs):
           """Create an instrument instance from a definition."""
           instrument_class = cls.create_class_from_definition(definition)
           
           # Instantiate with adapter
           instance = instrument_class(
               name=definition.get('display_name', definition['name']),
               **kwargs
           )
           
           if adapter:
               instance.adapter = adapter
           
           return instance
   ```

2. **Update InstrumentSelectorWidget** to load from database:

   ```python
   def load_instruments_from_database(self):
       """Load instrument definitions from database."""
       if not self.db_service:
           return
       
       definitions = self.db_service.get_instrument_definitions(
           lab_id=self.current_lab_id
       )
       
       for defn in definitions:
           # Create a tree item for each definition
           item = QTreeWidgetItem([defn['display_name']])
           item.setData(0, Qt.UserRole, {
               'source': 'database',
               'definition_id': defn['id'],
               'definition': defn,
           })
           self.add_to_category(defn['category'], item)
   ```

#### Deliverables
- [ ] InstrumentFactory class
- [ ] Updated InstrumentSelectorWidget
- [ ] Integration with existing file-based loading

---

### Phase 4: Computer Binding & Auto-Discovery (Week 3)

#### Tasks

1. **Create ComputerIdentifier utility**:

   ```python
   # pybirch/utils/computer_id.py
   
   import socket
   import uuid
   import os
   
   def get_computer_info() -> dict:
       """Get identifying information about this computer."""
       return {
           'computer_name': socket.gethostname(),
           'computer_id': str(uuid.getnode()),  # MAC address as int
           'username': os.getenv('USERNAME') or os.getenv('USER'),
           'os': os.name,
       }
   ```

2. **Implement auto-discovery on startup**:

   ```python
   # In GUI/main/pages/instruments_page.py or similar
   
   def discover_instruments_for_this_computer(self):
       """Load instruments bound to this computer from database."""
       computer_info = get_computer_info()
       
       bindings = self.db_service.get_computer_bindings(
           computer_name=computer_info['computer_name']
       )
       
       for binding in bindings:
           instrument = binding['instrument']
           definition = instrument.get('definition')
           
           if definition:
               # Create instance from database definition
               instance = InstrumentFactory.create_instance(
                   definition,
                   adapter=binding['adapter']
               )
               self.add_configured_instrument(instance, binding)
   ```

3. **Update adapter binding to save to database**:

   ```python
   def on_adapter_assigned(self, instrument, adapter):
       """Called when user assigns an adapter to an instrument."""
       # ... existing logic ...
       
       # NEW: Save to database
       if self.db_service and instrument.definition_id:
           self.db_service.bind_instrument_to_computer(
               instrument_id=instrument.database_id,
               computer_name=get_computer_info()['computer_name'],
               adapter=adapter,
           )
   ```

#### Deliverables
- [ ] ComputerIdentifier utility
- [ ] Auto-discovery on PyBirch startup
- [ ] Adapter binding persistence

---

### Phase 5: Web UI for Instrument Creation (Week 3-4)

#### Tasks

1. **Create instrument editor page** in web UI:

   ```
   database/web/templates/instruments/
   ├── list.html           # List all instrument definitions
   ├── create.html         # Create new instrument
   ├── edit.html           # Edit existing instrument
   └── code_editor.html    # Monaco/CodeMirror code editor
   ```

2. **Add API endpoints**:

   ```python
   # database/web/routes/instruments.py
   
   @bp.route('/api/instrument-definitions', methods=['GET'])
   def list_definitions():
       """List all instrument definitions."""
       
   @bp.route('/api/instrument-definitions', methods=['POST'])
   def create_definition():
       """Create a new instrument definition."""
       
   @bp.route('/api/instrument-definitions/<int:id>', methods=['PUT'])
   def update_definition(id):
       """Update an instrument definition (creates new version)."""
       
   @bp.route('/api/instrument-definitions/<int:id>/validate', methods=['POST'])
   def validate_code(id):
       """Validate instrument code syntax and structure."""
   ```

3. **Code editor with validation**:
   - Monaco editor with Python syntax highlighting
   - Real-time syntax validation
   - Base class template insertion
   - Preview of settings schema

#### Deliverables
- [ ] Web UI pages
- [ ] REST API endpoints
- [ ] Code editor integration
- [ ] Validation logic

---

### Phase 6: Sync & Versioning (Week 4)

#### Tasks

1. **Implement sync on PyBirch startup**:
   - Check for updated definitions
   - Download new versions
   - Invalidate class cache if code changed

2. **Version comparison UI**:
   - Show diff between versions
   - Allow rollback to previous version

3. **Conflict resolution**:
   - Handle case where instrument in use has updated definition
   - Option to reload or continue with cached version

#### Deliverables
- [ ] Sync mechanism
- [ ] Version comparison UI
- [ ] Conflict resolution

---

## Code Examples

### Example: Creating Instrument via Web UI

```python
# User fills out form in browser:
definition = {
    "name": "MyLockIn",
    "display_name": "My Lock-In Amplifier",
    "instrument_type": "measurement",
    "category": "Lock-In Amplifiers",
    "manufacturer": "Stanford Research",
    "base_class": "VisaBaseMeasurementInstrument",
    "source_code": '''
class MyLockIn(VisaBaseMeasurementInstrument):
    """Custom lock-in amplifier implementation."""
    
    def __init__(self, name="My Lock-In", adapter=""):
        super().__init__(name, adapter)
        self.data_columns = np.array(["X", "Y", "R", "Theta"])
        self.data_units = np.array(["V", "V", "V", "deg"])
        self._define_settings({
            "sensitivity": 1e-6,
            "time_constant": 0.1,
        })
    
    def _connect_impl(self) -> bool:
        try:
            idn = self.instrument.query("*IDN?")
            return "SR830" in idn or "SR860" in idn
        except:
            return False
    
    def _perform_measurement_impl(self) -> np.ndarray:
        x = float(self.instrument.query("OUTP? 1"))
        y = float(self.instrument.query("OUTP? 2"))
        r = float(self.instrument.query("OUTP? 3"))
        theta = float(self.instrument.query("OUTP? 4"))
        return np.array([[x, y, r, theta]])
''',
    "data_columns": ["X", "Y", "R", "Theta"],
    "data_units": ["V", "V", "V", "deg"],
    "settings_schema": {
        "type": "object",
        "properties": {
            "sensitivity": {"type": "number", "minimum": 1e-9, "maximum": 1},
            "time_constant": {"type": "number", "minimum": 0.001, "maximum": 30}
        }
    }
}

# API call creates it
response = requests.post('/api/instrument-definitions', json=definition)
```

### Example: Auto-Discovery on Startup

```python
# When PyBirch starts on LABPC-01:

computer_info = get_computer_info()
# {'computer_name': 'LABPC-01', 'computer_id': '...', 'username': 'researcher'}

# Query database for instruments bound to this computer
bindings = db_service.get_computer_bindings(computer_name='LABPC-01')

# Returns:
[
    {
        'instrument': {
            'id': 42,
            'name': 'Main Lock-In',
            'definition_id': 15,
            'definition': {
                'name': 'MyLockIn',
                'source_code': '...',
                ...
            }
        },
        'adapter': 'GPIB::8::INSTR',
        'last_connected': '2026-01-06T10:30:00',
        'last_settings': {'sensitivity': 1e-6, ...}
    },
    ...
]

# Create instances from definitions
for binding in bindings:
    instrument = InstrumentFactory.create_instance(
        binding['instrument']['definition'],
        adapter=binding['adapter']
    )
    instrument.settings = binding.get('last_settings', {})
    instrument_manager.add_configured(instrument)
```

---

## Security Considerations

### Code Execution Safety

1. **Sandboxing**: Use `RestrictedPython` or similar to limit what database-stored code can do:
   - No file system access
   - No network access (except via VISA)
   - No subprocess spawning
   - Limited imports

2. **Code Review Workflow**:
   - New definitions require approval before use
   - `is_approved` flag on InstrumentDefinition
   - Admin can approve/reject submissions

3. **Audit Trail**:
   - All code changes logged
   - User attribution
   - Timestamp tracking

### Database Security

1. **Access Control**:
   - Only lab admins can create/modify definitions
   - Regular users can only use approved definitions
   - Per-lab visibility controls

2. **Backup Strategy**:
   - Regular backups of instrument_definitions table
   - Point-in-time recovery capability

---

## Migration Path for Existing Users

### Backward Compatibility

1. **File-based instruments still work**:
   - InstrumentSelectorWidget checks both database AND file system
   - Database definitions take precedence if same name exists

2. **Gradual migration**:
   - Users can migrate instruments one at a time
   - No forced cutover

3. **Export capability**:
   - Database definitions can be exported as .py files
   - Enables offline development and testing

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| 1. Schema & Migration | Week 1 | New tables, migration, CRUD ops |
| 2. Code Migration Tool | Week 1-2 | Existing instruments in DB |
| 3. Dynamic Loading | Week 2 | InstrumentFactory, UI integration |
| 4. Computer Binding | Week 3 | Auto-discovery, adapter persistence |
| 5. Web UI | Week 3-4 | Browser-based instrument editor |
| 6. Sync & Versioning | Week 4 | Version control, sync mechanism |

**Total: ~4 weeks**

---

## Future Enhancements

1. **Instrument Marketplace**:
   - Public repository of instrument definitions
   - Community contributions
   - Rating/review system

2. **AI-Assisted Instrument Creation**:
   - Upload instrument manual
   - LLM generates initial code
   - Human review and refinement

3. **Real-time Collaboration**:
   - Multiple users editing same definition
   - Live preview across connected PyBirch instances

4. **Instrument Testing Framework**:
   - Automated tests for definitions
   - Simulated hardware for CI/CD
   - Regression testing on updates
