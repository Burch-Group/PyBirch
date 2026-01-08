# WebSocket Integration Implementation Notes

## Session: 2026-01-07

### Objective
Integrate PyBirch GUI queue/scan execution with the WebSocket server so the web dashboard receives live updates.

---

## Architecture Summary

### Existing Components
1. **Queue Callbacks** (`pybirch/queue/queue.py`):
   - `add_log_callback(callback)` - receives log entries
   - `add_state_callback(callback)` - receives progress updates
   - `add_progress_callback(callback)` - receives progress updates

2. **Scan Extensions** (`pybirch/scan/scan.py`):
   - `ScanExtension` base class with lifecycle hooks
   - `startup()`, `execute()`, `save_data()`, `shutdown()` - standard hooks
   - Extensions registered via `Scan.extensions` list

3. **WebSocket Server** (`pybirch/database_integration/sync/websocket_server.py`):
   - `ScanUpdateServer` with broadcast methods
   - Room-based subscriptions for targeted updates

4. **Database Extensions** (`pybirch/database_integration/`):
   - `DatabaseExtension` - persists scans to database
   - `DatabaseQueue` / `DatabaseQueueExtension` - queue persistence

### Integration Gap (FIXED)
The event handlers exist but were **NOT wired** to the queue callbacks or scan extensions.

---

## Implementation Progress

### ✅ Phase 1: Create Integration Bridge Module
**Status**: COMPLETED

Created `pybirch/database_integration/sync/websocket_integration.py`:
- `WebSocketQueueBridge` - connects Queue callbacks → WebSocket broadcasts
  - Registers with `add_log_callback`, `add_state_callback`, `add_progress_callback`
  - Forwards events to `ScanUpdateServer` broadcast methods
- `WebSocketScanExtension` - ScanExtension that broadcasts events
  - Implements `startup()`, `execute()`, `save_data()`, `shutdown()`
  - Broadcasts data points as scan collects data
- `setup_websocket_integration()` - helper to create bridge
- `create_websocket_scan_extension()` - helper to create scan extension

### ✅ Phase 2: Wire to DatabaseExtension
**Status**: COMPLETED (via separate extension)

Created `WebSocketScanExtension` that can be added alongside `DatabaseExtension`:
- Both extensions can be in `scan.extensions` list
- Each handles its own concerns (persistence vs broadcasting)

### ✅ Phase 3: Wire to DatabaseQueue
**Status**: COMPLETED

Modified `DatabaseQueue` in `pybirch/database_integration/extensions/database_queue.py`:
- Added `update_server` parameter to accept `ScanUpdateServer`
- Added `_setup_websocket_integration()` method
- Added `enable_websocket_integration(update_server)` method
- Added `disable_websocket_integration()` method

### ✅ Phase 4: Data Point Streaming
**Status**: COMPLETED

`WebSocketScanExtension.save_data()` broadcasts data points via `broadcast_data_point()`.
- Respects `data_point_interval` setting to throttle broadcasts
- Converts DataFrame rows to dict for JSON serialization

### ✅ Phase 5: Create Flask App Integration
**Status**: COMPLETED

Modified `database/web/app.py`:
- Added global `scan_update_server` variable
- Added `get_scan_update_server()` function
- `create_app()` now creates and registers `ScanUpdateServer`

### ⏳ Phase 6: GUI Integration
**Status**: IN PROGRESS

Next Steps:
1. Add method to MainWindow to enable WebSocket integration
2. Connect to running Flask-SocketIO server
3. Test live updates

### ⬜ Phase 7: Testing
**Status**: NOT STARTED

---

## Usage Examples

### Enable WebSocket for an existing Queue
```python
from pybirch.database_integration.sync import setup_websocket_integration
from database.web.app import get_scan_update_server

# Get the server from the Flask app
update_server = get_scan_update_server()

# Setup integration for a queue
bridge = setup_websocket_integration(queue, update_server)
```

### Add WebSocket extension to a Scan
```python
from pybirch.database_integration.sync import create_websocket_scan_extension
from database.web.app import get_scan_update_server

update_server = get_scan_update_server()
ext = create_websocket_scan_extension(update_server, scan_id="SCAN_001")
scan.extensions.append(ext)
```

### Enable on DatabaseQueue
```python
from pybirch.database_integration.extensions import DatabaseQueue
from database.web.app import get_scan_update_server

# Create queue with WebSocket integration
queue = DatabaseQueue(db_service, update_server=get_scan_update_server())

# Or enable later
queue.enable_websocket_integration(get_scan_update_server())
```

### Enable in GUI MainWindow
```python
from GUI.main.main_window import MainWindow

window = MainWindow(queue=my_queue)
window.enable_websocket_integration()  # Auto-gets server from Flask app
```

---

## Testing Summary

✅ All 219 tests pass
✅ WebSocket integration module imports correctly
✅ GUI MainWindow imports with WEBSOCKET_AVAILABLE=True

---

## Files Created/Modified

### New Files
- `pybirch/database_integration/sync/websocket_integration.py` - Bridge module

### Modified Files
- `pybirch/database_integration/sync/__init__.py` - Added exports
- `pybirch/database_integration/extensions/database_queue.py` - Added WebSocket support
- `database/web/app.py` - Added global ScanUpdateServer
- `database/run_web.py` - Fixed to use socketio.run()
- `GUI/main/main_window.py` - Added enable_websocket_integration(), show_extensions_page()
- `GUI/windows/extensions_page.py` - NEW: Extensions management page
- `tests/test_websocket_integration.py` - NEW: WebSocket integration tests

---

## Important Notes

### PowerShell + Conda
**IMPORTANT**: In PowerShell, conda environments do NOT persist through semicolons.

❌ Wrong: `conda activate pybirch; python script.py`
✅ Correct: `conda run -n pybirch python script.py`

Always use `conda run -n <env>` for running commands in a specific conda environment in PowerShell.

---

## Test Results

### Test Suite: 222 tests passed ✅

### WebSocket Integration Tests:
1. ✅ **WebSocket Bridge Events** - Verifies queue callbacks are forwarded to WebSocket broadcasts
2. ✅ **WebSocket Scan Extension** - Verifies scan lifecycle events are broadcast
3. ✅ **Full Integration** - Verifies end-to-end queue execution with WebSocket

Run tests: `conda run -n pybirch python tests/test_websocket_integration.py`
