# Instrument Database Storage - Implementation Notes

## Current Status: Phase 5 In Progress (Auto-Discovery)

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
- [ ] Computer binding Web UI
- [ ] Unit tests written
- [ ] Web UI for browser-based creation

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
- `GUI/widgets/instrument_autoload.py` - Added database instrument loading
- `GUI/windows/instruments_page.py` - Added set_database_service method
- `GUI/main/main_window.py` - Passes db_service to instruments page
- `scripts/test_factory.py` - Test script for factory

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
