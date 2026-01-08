# Issues Tracker

## Active Issues

### Issue #4: High-dimensional scan support missing
**Status**: PENDING
**Priority**: MEDIUM
**Description**: Scans with 4+ movement objects need visualization support
**Requirements**:
- Store movement positions in data point extra_data
- Allow filtering by position
- Support dimension reduction for visualization

### Issue #5: Dimension reduction UI not yet implemented
**Status**: PENDING
**Priority**: LOW
**Description**: Add slice/max/min/average controls for dimension reduction
**Requirements**:
- Add dimension reduction panel to UI
- Implement slice slider
- Add projection method selection
- Document in DIMENSION_REDUCTION.md (already created)

---

## Resolved Issues

### Issue #1: Visualizations are blank [RESOLVED]
**Status**: RESOLVED
**Priority**: HIGH
**Resolution**: 
- Created new `get_visualization_data()` method in services.py
- Rewrote scan_detail.html template with proper Chart.js integration
- Data now correctly extracted from `p.values` dict

### Issue #2: X-axis shows point index instead of actual values [RESOLVED]
**Status**: RESOLVED
**Priority**: HIGH
**Resolution**: 
- Charts now use actual column values for X-axis
- First column of measurement is used as X-axis by default
- Second column used as Y-axis
- Axis selectors allow changing which columns to plot

### Issue #3: No per-measurement visualization [RESOLVED]
**Status**: RESOLVED
**Priority**: MEDIUM
**Resolution**: 
- Each measurement object now gets its own chart
- Tabbed interface for scans with multiple measurements
- Data grouped by measurement object name

---

## Integration Phase Issues (2026-01-06)

### Issue #6: InstrumentStatus Model Missing
**Status**: RESOLVED ✅
**Priority**: HIGH
**Description**: The `InstrumentStatus` model from INTEGRATION_PLAN.md is not yet in models.py

**Resolution**: Added InstrumentStatus model to database/models.py after Instrument class.
Created migration script at database/migrations/add_instrument_status.py

---

### Issue #7: sync/ Directory Missing
**Status**: RESOLVED ✅
**Priority**: HIGH
**Description**: WebSocket infrastructure for Phase 4 not created

**Resolution**: Created complete sync directory with:
- `pybirch/database_integration/sync/__init__.py`
- `pybirch/database_integration/sync/websocket_server.py`
- `pybirch/database_integration/sync/event_handlers.py`

---

### Issue #8: Flask-SocketIO Not Integrated
**Status**: RESOLVED ✅
**Priority**: HIGH
**Description**: Web app doesn't support WebSockets yet

**Resolution**: 
1. Updated database/web/app.py with optional flask-socketio support
2. Added graceful fallback when flask-socketio not installed
3. Registered WebSocket event handlers for scan/queue/instrument subscriptions
4. Added get_socketio() function for external access

---

### Issue #9: Run Migration Script
**Status**: RESOLVED ✅
**Priority**: MEDIUM
**Description**: Need to run the new migration to create instrument_status table

**Command run:**
```bash
python database\migrations\add_instrument_status.py --db database\pybirch.db
```

**Result:** Successfully created instrument_status table with indexes.

---

### Issue #10: Install flask-socketio Dependency
**Status**: PENDING
**Priority**: MEDIUM
**Description**: flask-socketio package needs to be installed for WebSocket support

**Command to run:**
```bash
pip install flask-socketio
```

---


### Enhancement #2: Export to CSV/JSON
**Description**: Download measurement data for external analysis
**Benefit**: Integration with other tools

### Enhancement #3: Real-time plotting during scan
**Description**: Live updates as data comes in
**Benefit**: Monitor scan progress
