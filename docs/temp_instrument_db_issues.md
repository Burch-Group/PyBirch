# Instrument Database Storage - Issues

## Open Issues

### Web UI Needed
- [ ] Create instrument editor page with code editor
- [ ] Add REST API endpoints for definitions
- [ ] Implement code validation endpoint

### Testing Needed
- [ ] Unit tests for InstrumentFactory
- [ ] Integration tests for CRUD operations

### Known Limitations
- [ ] Some instruments have module-level dependencies (e.g., FakeXStage needs FakeLinearStageController)
- [ ] Need to handle dependent classes in source_code or add import support

## Resolved Issues

### Phase 1-3 Complete
- ✓ Database schema designed and implemented
- ✓ CRUD methods added to DatabaseService
- ✓ InstrumentFactory supports dynamic class creation
- ✓ Migration script extracts existing instruments
- ✓ Computer binding tracks last adapter/computer

### Phase 4 Complete - GUI Integration
- ✓ `InstrumentAutoLoadWidget` updated with `_load_database_instruments()` method
- ✓ Database instruments shown under "📦 Database Instruments" section in tree
- ✓ `set_database_service()` method added to widget and page
- ✓ MainWindow propagates database service to instruments page
- ✓ 7 fake instruments successfully migrated and loadable

## Questions to Address
1. ~~Should `source_code` be validated on save?~~ → Yes, use InstrumentFactory.validate_source_code()
2. ~~How to handle import dependencies in dynamic exec?~~ → Namespace includes np, pd, time, math, base classes
3. Security sandbox requirements? → Future enhancement, add RestrictedPython if needed

## Next Steps
1. Run migration on test database
2. Integrate with GUI InstrumentSelectorWidget
3. Create web UI for browser-based instrument creation
