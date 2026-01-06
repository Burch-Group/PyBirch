# PyBirch Database & Measurement Integration Plan

## Executive Summary

This document outlines a comprehensive plan to integrate PyBirch's measurement and instrument control framework with the database web UI. The goal is to enable real-time tracking of experiments, automatic data persistence, and full traceability from sample creation through measurement and analysis.

---

## 1. Architecture Overview

### Current Systems

#### PyBirch Measurement Framework (`pybirch/`)
- **Scan System** (`scan/scan.py`): Orchestrates measurements with `Scan` and `ScanSettings` classes
- **Measurements** (`scan/measurements.py`): Base classes for measurement instruments (`Measurement`, `VisaMeasurement`, `MeasurementItem`)
- **Movements** (`scan/movements.py`): Base classes for positioning equipment (`Movement`, `VisaMovement`, `MovementItem`)
- **Queue** (`queue/queue.py`): Thread-safe execution queue with `Queue`, `ScanHandle`, `ScanState`, `QueueState`
- **Samples** (`queue/samples.py`): Simple `Sample` class with ID, material, tags
- **Instruments** (`Instruments/base.py`): Abstract instrument architecture with VISA support

#### Database System (`database/`)
- **Models** (`models.py`): SQLAlchemy ORM with comprehensive models for Labs, Projects, Samples, Scans, Queues, Equipment, Measurements, Analysis
- **Services** (`services.py`): Business logic layer for CRUD operations
- **Web UI** (`web/`): Flask-based interface with authentication

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Web UI (Flask)                                   │
│   - Dashboard with live scan status                                      │
│   - Queue management interface                                           │
│   - Equipment status monitoring                                          │
│   - Data visualization                                                   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Integration Layer (NEW)                             │
│   - ScanManager: Bridges PyBirch Scan ↔ DB Scan                         │
│   - QueueManager: Bridges PyBirch Queue ↔ DB Queue                      │
│   - EquipmentManager: Bridges Instruments ↔ DB Equipment                │
│   - DataManager: Handles measurement data persistence                    │
│   - WebSocket Server: Real-time updates to UI                           │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   Database Layer    │  │ PyBirch Framework   │  │   External Data     │
│   (SQLAlchemy)      │  │ (Instruments/Scans) │  │   (W&B, Files)      │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

---

## 2. Class Mapping & Integration Points

### 2.1 Sample Integration

| PyBirch Class | Database Model | Integration Strategy |
|---------------|----------------|---------------------|
| `Sample` (queue/samples.py) | `Sample` (models.py) | Bidirectional conversion |

**Implementation:**

```python
# Already exists in models.py - enhance with full sync
class Sample(Base):
    def to_pybirch_sample(self):
        """Convert to PyBirch Sample object."""
        from pybirch.queue.samples import Sample as PyBirchSample
        return PyBirchSample(
            ID=self.sample_id,
            material=self.material or '',
            additional_tags=self.additional_tags or [],
            image=self._load_image()  # Load from image_path
        )
    
    @classmethod
    def from_pybirch_sample(cls, pybirch_sample, **kwargs):
        """Create from PyBirch Sample object."""
        ...
```

**Tasks:**
- [ ] Add image loading/saving functionality
- [ ] Create sync mechanism to update database when PyBirch sample changes
- [ ] Add sample validation before scan starts

### 2.2 Scan Integration

| PyBirch Class | Database Model | Integration Strategy |
|---------------|----------------|---------------------|
| `ScanSettings` | `ScanTemplate` / `Scan` | Template for config, Scan for execution |
| `Scan` | `Scan` | Real-time status sync |

**Key Fields Mapping:**

```
ScanSettings.project_name    → Scan.project_name, ScanTemplate.name
ScanSettings.scan_name       → Scan.scan_name
ScanSettings.scan_type       → Scan.scan_type, ScanTemplate.scan_type
ScanSettings.job_type        → Scan.job_type, ScanTemplate.job_type
ScanSettings.scan_tree       → Scan.scan_tree_data (serialized JSON)
ScanSettings.extensions      → Scan.extra_data['extensions']
ScanSettings.user_fields     → Scan.extra_data['user_fields']
```

**Implementation Tasks:**
- [ ] Create `ScanSyncExtension` class to auto-sync scan state to database
- [ ] Implement `scan_tree` serialization/deserialization
- [ ] Add hooks for scan lifecycle events (start, pause, resume, complete, abort)

### 2.3 Queue Integration

| PyBirch Class | Database Model | Integration Strategy |
|---------------|----------------|---------------------|
| `Queue` | `Queue` | Real-time sync with WebSocket updates |
| `ScanHandle` | `Scan` (with queue_id) | Track individual scan state |
| `LogEntry` | `QueueLog` (NEW) | Persist queue logs |

**State Mapping:**

```python
# PyBirch QueueState → DB Queue.status
QueueState.IDLE     → 'idle'
QueueState.RUNNING  → 'running'
QueueState.PAUSED   → 'paused'
QueueState.STOPPING → 'stopping'

# PyBirch ScanState → DB Scan.status
ScanState.QUEUED    → 'queued'
ScanState.RUNNING   → 'running'
ScanState.PAUSED    → 'paused'
ScanState.COMPLETED → 'completed'
ScanState.ABORTED   → 'aborted'
ScanState.FAILED    → 'failed'
```

**Implementation Tasks:**
- [ ] Create `DatabaseQueue` subclass that wraps `Queue` with DB persistence
- [ ] Add `QueueLog` model for storing queue logs
- [ ] Implement queue recovery from database on restart

### 2.4 Equipment/Instrument Integration

| PyBirch Class | Database Model | Integration Strategy |
|---------------|----------------|---------------------|
| `BaseMeasurementInstrument` | `Equipment` (type='measurement') | Registration & status tracking |
| `Movement` / `VisaMovement` | `Equipment` (type='movement') | Registration & status tracking |
| `MeasurementItem` | `MeasurementObject` | Store measurement config |

**Key Fields Mapping:**

```
Instrument.name              → Equipment.name
Instrument.adapter           → Equipment.adapter
Instrument.__class__.__name__ → Equipment.pybirch_class
Instrument.settings          → Equipment.specifications (JSON)
Instrument.data_columns      → MeasurementObject.columns
Instrument.data_units        → MeasurementObject.unit
```

**Implementation Tasks:**
- [ ] Create equipment registry that auto-discovers instruments from setups
- [ ] Add instrument status monitoring (connected/disconnected/error)
- [ ] Track calibration dates and maintenance schedules
- [ ] Store last-known settings for quick setup

### 2.5 Measurement Data Integration

| PyBirch Data Flow | Database Model | Storage Strategy |
|-------------------|----------------|------------------|
| `Scan.save_data()` | `MeasurementDataPoint` | Row-by-row for numeric |
| DataFrame rows | `MeasurementDataPoint.values` (JSON) | Flexible column storage |
| Spectra/Images | `MeasurementDataArray` | Binary blob or file path |

**Implementation Tasks:**
- [ ] Create `DatabaseExtension` class for PyBirch scan extensions
- [ ] Implement buffered batch inserts for high-frequency data
- [ ] Add data compression for large datasets
- [ ] Create data export functions (CSV, HDF5, etc.)

---

## 3. New Components to Create

### 3.1 Integration Layer (`pybirch/database_integration/`)

```
pybirch/database_integration/
├── __init__.py
├── managers/
│   ├── __init__.py
│   ├── scan_manager.py      # ScanManager class
│   ├── queue_manager.py     # QueueManager class  
│   ├── equipment_manager.py # EquipmentManager class
│   └── data_manager.py      # DataManager class
├── extensions/
│   ├── __init__.py
│   └── database_extension.py # PyBirch extension for DB sync
├── sync/
│   ├── __init__.py
│   ├── websocket_server.py  # Real-time updates
│   └── event_handlers.py    # Scan/Queue event handlers
└── utils/
    ├── __init__.py
    ├── serializers.py       # Object serialization helpers
    └── validators.py        # Data validation
```

### 3.2 Database Extension for PyBirch

```python
# pybirch/database_integration/extensions/database_extension.py

from pybirch.extensions.base import BaseExtension
from database.services import DatabaseService

class DatabaseExtension(BaseExtension):
    """Extension that syncs scan data to the database."""
    
    def __init__(self, db_service: DatabaseService, scan_id: int):
        self.db = db_service
        self.scan_id = scan_id
        self._measurement_objects = {}  # Cache measurement object IDs
    
    def execute(self):
        """Called when scan starts."""
        self.db.update_scan(self.scan_id, status='running', started_at=datetime.now())
    
    def save_data(self, data: pd.DataFrame, measurement_name: str):
        """Called by Scan.save_data() for each measurement."""
        # Get or create measurement object
        if measurement_name not in self._measurement_objects:
            mo = self.db.create_measurement_object(
                scan_id=self.scan_id,
                name=measurement_name,
                columns=list(data.columns)
            )
            self._measurement_objects[measurement_name] = mo.id
        
        mo_id = self._measurement_objects[measurement_name]
        
        # Batch insert data points
        data_points = []
        for idx, row in data.iterrows():
            data_points.append({
                'measurement_object_id': mo_id,
                'sequence_index': idx,
                'values': row.to_dict(),
                'timestamp': datetime.now()
            })
        
        self.db.bulk_create_data_points(data_points)
    
    def on_complete(self):
        """Called when scan completes."""
        self.db.update_scan(self.scan_id, status='completed', completed_at=datetime.now())
    
    def on_error(self, error: Exception):
        """Called on scan error."""
        self.db.update_scan(self.scan_id, status='failed', 
                          extra_data={'error': str(error)})
```

### 3.3 New Database Models

```python
# Add to database/models.py

class QueueLog(Base):
    """Log entries from queue execution."""
    __tablename__ = "queue_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    queue_id: Mapped[int] = mapped_column(Integer, ForeignKey('queues.id'))
    scan_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    level: Mapped[str] = mapped_column(String(20))  # INFO, WARNING, ERROR
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    queue: Mapped["Queue"] = relationship("Queue", backref="logs")


class InstrumentStatus(Base):
    """Real-time instrument status tracking."""
    __tablename__ = "instrument_status"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(Integer, ForeignKey('equipment.id'))
    status: Mapped[str] = mapped_column(String(50))  # connected, disconnected, error, busy
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime)
    current_settings: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    equipment: Mapped["Equipment"] = relationship("Equipment", backref="status_history")
```

### 3.4 WebSocket Server for Real-Time Updates

```python
# pybirch/database_integration/sync/websocket_server.py

from flask_socketio import SocketIO, emit

class ScanUpdateServer:
    """WebSocket server for real-time scan updates."""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
    
    def broadcast_scan_status(self, scan_id: str, status: str, progress: float = None):
        """Broadcast scan status update to all connected clients."""
        self.socketio.emit('scan_status', {
            'scan_id': scan_id,
            'status': status,
            'progress': progress,
            'timestamp': datetime.now().isoformat()
        })
    
    def broadcast_queue_status(self, queue_id: str, status: str, current_scan: str = None):
        """Broadcast queue status update."""
        self.socketio.emit('queue_status', {
            'queue_id': queue_id,
            'status': status,
            'current_scan': current_scan,
            'timestamp': datetime.now().isoformat()
        })
    
    def broadcast_data_point(self, scan_id: str, measurement_name: str, data: dict):
        """Broadcast new data point for live plotting."""
        self.socketio.emit('data_point', {
            'scan_id': scan_id,
            'measurement': measurement_name,
            'data': data
        })
```

---

## 4. Web UI Enhancements

### 4.1 New Dashboard Components

```
database/web/templates/
├── dashboard/
│   ├── index.html           # Main dashboard with status overview
│   ├── live_scan.html       # Real-time scan monitoring
│   └── queue_control.html   # Queue start/stop/pause controls
├── instruments/
│   ├── list.html            # Equipment list with status
│   ├── detail.html          # Individual instrument details
│   └── settings.html        # Configure instrument settings
├── data/
│   ├── viewer.html          # Data visualization
│   └── export.html          # Data export options
```

### 4.2 JavaScript for Real-Time Updates

```javascript
// database/web/static/js/scan_monitor.js

const socket = io();

socket.on('scan_status', function(data) {
    updateScanStatusUI(data.scan_id, data.status, data.progress);
});

socket.on('data_point', function(data) {
    addDataPointToChart(data.scan_id, data.measurement, data.data);
});

socket.on('queue_status', function(data) {
    updateQueueStatusUI(data.queue_id, data.status, data.current_scan);
});
```

### 4.3 New Routes

```python
# database/web/routes.py additions

@app.route('/api/queue/<queue_id>/start', methods=['POST'])
@login_required
def start_queue(queue_id):
    """Start a queue from the web interface."""
    ...

@app.route('/api/scan/<scan_id>/pause', methods=['POST'])
@login_required
def pause_scan(scan_id):
    """Pause a running scan."""
    ...

@app.route('/api/instruments/status')
@login_required
def get_instrument_status():
    """Get current status of all instruments."""
    ...

@app.route('/api/scan/<scan_id>/data/<measurement_name>')
@login_required
def get_scan_data(scan_id, measurement_name):
    """Get measurement data for visualization."""
    ...
```

---

## 5. Implementation Phases

### Phase 1: Foundation (Week 1-2) ✅ COMPLETED

**Status:** All components implemented.

**Completed items:**
1. ✅ Create integration layer directory structure (`pybirch/database_integration/`)
2. ✅ Implement basic serializers for PyBirch objects (`utils/serializers.py`)
3. ✅ Add validation utilities (`utils/validators.py`)
4. ✅ Create manager classes:
   - `ScanManager` - bridges PyBirch Scan ↔ database
   - `QueueManager` - bridges PyBirch Queue ↔ database
   - `EquipmentManager` - bridges instruments ↔ database
   - `DataManager` - handles buffered data persistence
5. ✅ Create `DatabaseExtension` for PyBirch scans
6. ✅ Create `DatabaseQueueExtension` for queue tracking
7. ✅ Add scan/queue CRUD methods to DatabaseService
8. ✅ Create usage examples (`examples/database_integration_example.py`)

**Files created:**
- `pybirch/database_integration/__init__.py`
- `pybirch/database_integration/managers/__init__.py`
- `pybirch/database_integration/managers/scan_manager.py`
- `pybirch/database_integration/managers/queue_manager.py`
- `pybirch/database_integration/managers/equipment_manager.py`
- `pybirch/database_integration/managers/data_manager.py`
- `pybirch/database_integration/extensions/__init__.py`
- `pybirch/database_integration/extensions/database_extension.py`
- `pybirch/database_integration/utils/__init__.py`
- `pybirch/database_integration/utils/serializers.py`
- `pybirch/database_integration/utils/validators.py`
- `examples/database_integration_example.py`

**Remaining for Phase 1:**
- [ ] Add `QueueLog` and `InstrumentStatus` models to database/models.py
- [ ] Create database migration script
- [ ] Write unit tests for serialization

### Phase 2: Scan Integration (Week 3-4) ✅ COMPLETED

**Status:** All components implemented and tested.

**Completed items:**
1. ✅ Implement `DatabaseExtension` for PyBirch scans
2. ✅ Create `ScanManager` class
3. ✅ Add scan lifecycle hooks
4. ✅ Implement data point persistence
5. ✅ Test with fake instruments
6. ✅ Integrate with actual PyBirch Scan class

**Implementation details:**
- `DatabaseExtension` now properly inherits from `ScanExtension`
- Modified `Scan.startup()` to call `set_scan_reference()` on extensions that support it
- Added `shutdown()` method to `DatabaseExtension` for clean completion
- Created fake instruments for testing:
  - `FakeMultimeter` - voltage/current measurements with noise
  - `FakeSpectrometer` - spectrum data with configurable peaks
  - `FakeLockin` - X, Y, R, Theta lock-in amplifier data
  - `FakeStage` - linear stage with movement simulation
  - `FakePiezo` - piezo stage for fine positioning
  - `FakeTemperatureController` - temperature control simulation

**Test coverage:**
- `test_integration.py` includes:
  - Fake instrument functionality tests
  - Database manager tests (ScanManager, QueueManager, DataManager, EquipmentManager)
  - Full measurement flow tests with fake instruments
  - Multi-instrument measurement tests

**Files created:**
- `pybirch/database_integration/testing/__init__.py`
- `pybirch/database_integration/testing/fake_instruments.py`
- `pybirch/database_integration/testing/test_integration.py`

**Files modified:**
- `pybirch/scan/scan.py` - Added extension reference passing
- `pybirch/database_integration/extensions/database_extension.py` - Refactored to inherit from ScanExtension

### Phase 3: Queue Integration (Week 5-6) - ✅ COMPLETED

**Status:** All queue integration components implemented and tested successfully.

**Completed Tasks:**
1. ✅ Implement `QueueManager` class - DONE (Phase 1)
2. ✅ Create `DatabaseQueue` wrapper (inherits from PyBirch Queue)
3. ✅ Add queue recovery from database
4. ✅ Implement queue log persistence (QueueLog model added)
5. ✅ Test multi-scan queue execution

**Implementation Summary:**

Created `DatabaseQueue` class that extends PyBirch's `Queue` to automatically track queue execution in the database. This provides seamless integration between the queue system and database persistence layer.

**Key Features Implemented:**
- **Automatic Database Tracking:** Queue state automatically syncs to database on creation, start, pause, resume, and completion
- **Scan Extension Auto-Injection:** DatabaseExtension is automatically added to scans when enqueued
- **Real-Time Log Persistence:** All queue log entries are automatically persisted via callbacks
- **State Change Callbacks:** Scan state changes (running, paused, completed, failed, aborted) automatically update database
- **Progress Tracking:** Queue progress (completed/total scans) automatically maintained
- **Queue Recovery:** `from_database()` class method reconstructs queue from database state for crash recovery
- **Incomplete Scan Handling:** Methods to identify and mark incomplete scans after crashes

**Files Created:**
- `pybirch/database_integration/extensions/database_queue.py` (558 lines)
  - `DatabaseQueue` class extending PyBirch Queue
  - Automatic database record creation and synchronization
  - Callback integration for logs, state changes, and progress
  - Queue recovery functionality
  
- `pybirch/database_integration/testing/test_queue_integration.py` (622 lines)
  - `MockDatabaseService` for testing without actual database
  - `MockScan` and `MockScanSettings` for queue testing
  - Test classes for QueueManager, ScanManager, and DatabaseQueue integration
  - 15 comprehensive tests (12 passed, 3 skipped for pandas dependency)

**Files Modified:**
- `pybirch/database_integration/extensions/__init__.py` - Added DatabaseQueue export
- `pybirch/database_integration/__init__.py` - Added DatabaseQueue to public API, added conditional imports for pandas
- `pybirch/database_integration/managers/__init__.py` - Made DataManager import conditional (pandas dependency)
- `pybirch/database_integration/managers/scan_manager.py` - Added `get_scans_for_queue()` method

**Test Results:**
```
Ran 15 tests in 0.181s
OK (skipped=3)
```

- ✅ 12 tests passed covering:
  - Mock database service operations
  - QueueManager lifecycle (create, start, pause, resume, complete, stop)
  - ScanManager lifecycle (create, start, complete, fail, abort)
  - Queue progress tracking and logging
  - Multi-scan queue tracking
  - Queue recovery data retrieval

**Usage Example:**
```python
from pybirch.database_integration import DatabaseQueue
from database.services import DatabaseService

# Create a database-tracked queue
db = DatabaseService('path/to/db.db')
queue = DatabaseQueue(
    QID="experiment_queue",
    db_service=db,
    project_id=1,
    sample_id=1,
    operator="researcher"
)

# Add scans - DatabaseExtension automatically added
queue.enqueue(scan1)  # Tracks in database
queue.enqueue(scan2)

# Execute - real-time database sync
queue.start()
queue.wait_for_completion()

# Recovery after crash
recovered = DatabaseQueue.from_database(db, "experiment_queue")
incomplete_scans = recovered.get_incomplete_scans()
```

**Architecture Patterns:**
- **Inheritance-Based Extension:** DatabaseQueue extends Queue rather than wrapping it
- **Callback Integration:** Uses Queue's callback system for non-invasive database sync
- **Automatic Extension Injection:** Transparently adds DatabaseExtension to scans
- **Lazy Loading:** Extensions created on-demand when scans are enqueued
- **State Machine Mapping:** Maps PyBirch ScanState to database operations via callbacks

**Integration Points:**
- Integrates with Phase 1 managers (QueueManager, ScanManager)
- Uses Phase 2's DatabaseExtension for individual scan tracking
- Provides foundation for Phase 4's real-time WebSocket updates

### Phase 4: Real-Time Features (Week 7-8)
1. [ ] Set up Flask-SocketIO
2. [ ] Implement WebSocket server
3. Create live dashboard UI
4. Add real-time data plotting
5. Test with concurrent users

### Phase 5: Equipment Management (Week 9-10)
1. Implement `EquipmentManager` class
2. Create instrument discovery system
3. Add status monitoring
4. Build equipment configuration UI
5. Test with real instruments

### Phase 6: Polish & Documentation (Week 11-12)
1. Performance optimization
2. Error handling improvements
3. User documentation
4. API documentation
5. Final integration testing

---

## 6. Database Services Additions

```python
# database/services.py additions

class DatabaseService:
    # ... existing methods ...
    
    # Scan management
    def create_scan_from_pybirch(self, pybirch_scan, queue_id: int = None) -> Scan:
        """Create database scan from PyBirch Scan object."""
        ...
    
    def update_scan_status(self, scan_id: int, status: str, **kwargs) -> Scan:
        """Update scan status with optional extra fields."""
        ...
    
    def get_active_scans(self) -> List[Scan]:
        """Get all scans with status 'running' or 'paused'."""
        ...
    
    # Measurement data
    def create_measurement_object(self, scan_id: int, name: str, **kwargs) -> MeasurementObject:
        """Create a new measurement object for a scan."""
        ...
    
    def bulk_create_data_points(self, data_points: List[dict]) -> int:
        """Bulk insert measurement data points. Returns count inserted."""
        ...
    
    def get_measurement_data(self, measurement_object_id: int, 
                            start_index: int = None, 
                            end_index: int = None) -> List[MeasurementDataPoint]:
        """Get measurement data points with optional range filtering."""
        ...
    
    # Queue management
    def create_queue_from_pybirch(self, pybirch_queue) -> Queue:
        """Create database queue from PyBirch Queue object."""
        ...
    
    def get_queue_with_scans(self, queue_id: int) -> Queue:
        """Get queue with all associated scans."""
        ...
    
    def add_queue_log(self, queue_id: int, level: str, message: str, scan_id: str = None):
        """Add a log entry for a queue."""
        ...
    
    # Equipment management  
    def register_instrument(self, instrument, lab_id: int = None) -> Equipment:
        """Register a PyBirch instrument in the database."""
        ...
    
    def update_instrument_status(self, equipment_id: int, status: str, **kwargs):
        """Update instrument connection status."""
        ...
    
    def get_instruments_by_type(self, equipment_type: str) -> List[Equipment]:
        """Get all instruments of a specific type."""
        ...
```

---

## 7. Configuration

### Environment Variables

```bash
# .env additions

# Database
DATABASE_URL=sqlite:///pybirch.db

# WebSocket
SOCKETIO_ASYNC_MODE=threading
SOCKETIO_PING_INTERVAL=25
SOCKETIO_PING_TIMEOUT=120

# Data Storage
DATA_STORAGE_PATH=./data
MAX_BUFFER_SIZE=1000
FLUSH_INTERVAL_SECONDS=5

# Instrument Discovery
INSTRUMENT_SCAN_INTERVAL=60
AUTO_RECONNECT_ATTEMPTS=3
```

### Config File

```python
# config/integration_config.py

class IntegrationConfig:
    # Data buffering
    BUFFER_SIZE = 1000
    FLUSH_INTERVAL = 5.0  # seconds
    
    # WebSocket
    BROADCAST_INTERVAL = 0.5  # seconds between status updates
    
    # Equipment
    STATUS_CHECK_INTERVAL = 30  # seconds
    AUTO_RECONNECT = True
    RECONNECT_DELAY = 5  # seconds
    
    # Data storage
    USE_BLOB_STORAGE = False  # Store arrays in DB vs files
    COMPRESSION_ENABLED = True
    ARRAY_CHUNK_SIZE = 10000
```

---

## 8. Testing Strategy

### Unit Tests
- Serialization/deserialization of all PyBirch objects
- Database CRUD operations for new models
- Event handler logic

### Integration Tests
- Full scan workflow: create → execute → save data → complete
- Queue execution with multiple scans
- Equipment registration and status updates
- WebSocket message delivery

### End-to-End Tests
- Web UI queue control
- Live data visualization
- Multi-user concurrent access
- Error recovery scenarios

---

## 9. Migration Considerations

### Existing Data
- Create migration script for existing pickle-based samples
- Import historical scan data from W&B if available
- Map existing equipment to new schema

### Backwards Compatibility
- PyBirch framework should work without database integration
- Integration layer is opt-in via extension system
- Existing scripts continue to function

---

## 10. Future Enhancements

1. **Cloud Storage Integration**: Store large datasets in S3/Azure Blob
2. **Multi-Lab Support**: Federation of databases across labs
3. **Advanced Analytics**: Built-in analysis pipeline integration
4. **Mobile App**: React Native app for remote monitoring
5. **Automated Reporting**: Generate PDF reports from scan data
6. **ML Pipeline**: Integration with ML frameworks for automated analysis
7. **DOI/Publication**: Link scans to publications with DOI tracking

---

## Appendix A: Full Class Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PyBirch Framework                             │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│ │   Sample    │  │    Scan     │  │   Queue     │  │  Instrument │ │
│ │ - ID        │  │ - settings  │  │ - handles   │  │ - name      │ │
│ │ - material  │  │ - sample    │  │ - state     │  │ - adapter   │ │
│ │ - tags      │  │ - owner     │  │ - mode      │  │ - settings  │ │
│ └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │
└────────┼────────────────┼────────────────┼────────────────┼────────┘
         │                │                │                │
         ▼                ▼                ▼                ▼
┌────────────────────────────────────────────────────────────────────┐
│                     Integration Layer                               │
├────────────────────────────────────────────────────────────────────┤
│  SampleManager   ScanManager    QueueManager   EquipmentManager    │
│  - to_db()       - to_db()      - to_db()      - register()        │
│  - from_db()     - from_db()    - from_db()    - update_status()   │
│  - sync()        - sync()       - sync()       - sync()            │
└────────────────────────────────────────────────────────────────────┘
         │                │                │                │
         ▼                ▼                ▼                ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Database Models                                │
├────────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│ │ DB Sample   │  │  DB Scan    │  │  DB Queue   │  │ Equipment   │ │
│ │ - sample_id │  │ - scan_id   │  │ - queue_id  │  │ - adapter   │ │
│ │ - material  │  │ - status    │  │ - status    │  │ - pybirch   │ │
│ │ - project   │  │ - data      │  │ - scans[]   │  │   _class    │ │
│ └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│                         │                                           │
│                         ▼                                           │
│              ┌───────────────────┐                                  │
│              │ MeasurementObject │                                  │
│              │ - name            │                                  │
│              │ - columns         │                                  │
│              │ - data_points[]   │                                  │
│              └───────────────────┘                                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Appendix B: Quick Start Code Example

```python
# Example: Running a scan with database integration

from pybirch.scan.scan import Scan, ScanSettings
from pybirch.database_integration.extensions import DatabaseExtension
from pybirch.database_integration.managers import ScanManager
from database.services import DatabaseService

# Initialize database
db = DatabaseService('sqlite:///pybirch.db')

# Get or create sample
sample = db.get_sample_by_id('SAMPLE-001')
pybirch_sample = sample.to_pybirch_sample()

# Create scan settings
settings = ScanSettings(
    project_name="MyProject",
    scan_name="IV_Curve",
    scan_type="1D Scan",
    job_type="Transport"
)

# Create scan with database extension
scan_manager = ScanManager(db)
db_scan = scan_manager.create_scan(settings, sample_id=sample.id)

# Create PyBirch scan with database extension
db_extension = DatabaseExtension(db, db_scan.id)
pybirch_scan = Scan(settings, pybirch_sample, extensions=[db_extension])

# Execute - data automatically syncs to database
pybirch_scan.startup()
pybirch_scan.execute()

# Scan completion automatically recorded in database
print(f"Scan completed: {db_scan.scan_id}")
print(f"Data points recorded: {db.get_data_point_count(db_scan.id)}")
```

---

*Document Version: 1.0*  
*Last Updated: 2025*  
*Author: GitHub Copilot*
