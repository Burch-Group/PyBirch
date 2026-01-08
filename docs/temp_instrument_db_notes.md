# Instrument Database Storage - Implementation Notes

## Current Status: Phase 4 Complete (GUI Integration)

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
