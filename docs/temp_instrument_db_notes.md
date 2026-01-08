# Instrument Database Storage - Implementation Notes

## Current Status: Phase 2 Complete (Computer Binding Web UI)

### Progress
- [x] New models added to models.py
- [x] Migration script created (add_instrument_definitions.py)
- [x] DatabaseService CRUD methods added
- [x] InstrumentFactory created
- [x] Instrument migration script created
- [x] Database migration run - tables created
- [x] 7 fake instruments migrated to database
- [x] InstrumentAutoLoadWidget updated to load from database
- [x] InstrumentsPage integrated with database service
- [x] MainWindow passes database service on state change
- [x] Auto-discovery filter added to InstrumentAutoLoadWidget
- [x] DatabaseService.get_definition_ids_for_computer() method added
- [x] Computer binding Web UI (Phase 2 complete!)
- [ ] Unit tests written

### Key Decisions
1. `InstrumentDefinition` stores source_code as TEXT field
2. `ComputerBinding` uses hostname + MAC for identification
3. Existing `Instrument` model gets `definition_id` FK
4. Backward compatible - file-based instruments still work
5. Version history stored in `InstrumentDefinitionVersion` table

### Files Created/Modified
- `database/models.py` - Added InstrumentDefinition, InstrumentDefinitionVersion, ComputerBinding
- `database/services.py` - CRUD operations for definitions and bindings
- `database/migrations/add_instrument_definitions.py` - Migration script
- `scripts/migrate_instruments_to_database.py` - Extract existing instruments (with --filter option)
- `pybirch/Instruments/factory.py` - Dynamic class creation with instance-based db_service
- `GUI/widgets/instrument_autoload.py` - Added database instrument loading + auto-discovery filter
- `GUI/windows/instruments_page.py` - Added set_database_service method
- `GUI/main/main_window.py` - Passes db_service to instruments page
- `scripts/test_factory.py` - Test script for factory
- `database/web/routes.py` - Added routes for instrument instances and computer bindings
- `database/web/templates/instrument_instance_form.html` - Form to create instrument instances
- `database/web/templates/computer_binding_form.html` - Form to bind instruments to computers
- `database/web/templates/instrument_definition_detail.html` - Updated with instances and bindings UI

### How to Run Migration
```bash
# 1. Run database migration
python database/migrations/add_instrument_definitions.py --db database/pybirch.db

# 2. Migrate existing instruments (dry run first)
python scripts/migrate_instruments_to_database.py --db database/pybirch.db --dry-run
python scripts/migrate_instruments_to_database.py --db database/pybirch.db
```

### Notes
- Base classes: `FakeMeasurementInstrument`, `FakeMovementInstrument`, `VisaBaseMeasurementInstrument`, `VisaBaseMovementInstrument`
- Settings can use `_define_settings()` or custom property override
- InstrumentFactory caches compiled classes for performance
- `get_computer_info()` utility provides hostname/MAC/username

### Auto-Discovery Feature
The `InstrumentAutoLoadWidget` now supports auto-discovery filtering:
- **Checkbox**: "Show bound instruments only" toggle in the GUI
- **Behavior**: When checked, only shows database instruments that:
  - Have an instrument instance bound to this computer (via `ComputerBinding`), OR
  - Are marked as public (`is_public=True`)
- **Computer identification**: Uses hostname from `get_computer_info()`
- **API**: `filter_by_computer` property to get/set filter state programmatically

Usage in code:
```python
# Enable auto-discovery filter
widget = InstrumentAutoLoadWidget(directory, filter_by_computer=True)

# Or toggle at runtime
widget.filter_by_computer = True

# Get current computer info
print(widget.computer_info)  # {'computer_name': 'HOSTNAME', 'computer_id': '...', 'username': '...'}
```

### Computer Binding Web UI (Phase 2)

The web UI now supports full management of instrument instances and computer bindings.

**Architecture (3-tier model):**
```
InstrumentDefinition (the code/class)
    ↓ 1:many
Instrument (a physical device using that code)
    ↓ 1:many  
ComputerBinding (which computer can access that device)
```

**New Routes:**
- `GET/POST /instrument-definitions/<id>/instruments/new` - Create instrument instance
- `POST /instrument-definitions/<id>/instruments/<inst_id>/delete` - Delete instance
- `GET/POST /instruments/<id>/bindings/new` - Add computer binding
- `POST /instruments/<id>/bindings/<binding_id>/delete` - Remove binding

**Instrument Definition Detail Page now shows:**
- List of instrument instances using this definition
- Computer bindings for each instance (with adapter override support)
- Buttons to add instances and bindings

**Computer Identification (for bindings):**
- **Primary**: Hostname (`computer_name`) - stable and human-readable
- **Secondary**: MAC address (`computer_id`) - for disambiguation
- **Optional**: Username - for per-user filtering

The binding form pre-fills with the current computer's info using `get_computer_info()`.
