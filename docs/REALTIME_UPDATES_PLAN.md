# Real-Time Updates Implementation Plan

## Overview

Add real-time WebSocket-based updates to the PyBirch Database UI for:
1. **Queue status and progress**
2. **Scan status, progress, and live data**
3. **Instrument status and position tracking**

Designed for **scalability** to support many concurrent scans/queues across multiple users.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              PyBirch Lab                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │   Scan 1    │  │   Scan 2    │  │   Scan 3    │  │   Scan N    │          │
│  │ (Queue A)   │  │ (Queue A)   │  │ (Queue B)   │  │ (Queue C)   │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │ events         │                │                │                  │
│         ▼                ▼                ▼                ▼                  │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │                    Event Handlers                                 │        │
│  │  ScanEventHandler | QueueEventHandler | InstrumentEventHandler   │        │
│  └───────────────────────────────┬──────────────────────────────────┘        │
│                                  │                                            │
│                                  ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │                    ScanUpdateServer                               │        │
│  │  (Flask-SocketIO with room-based routing)                        │        │
│  └───────────────────────────────┬──────────────────────────────────┘        │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │ WebSocket (Socket.IO protocol)
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Browser Clients                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │  Dashboard UI   │  │  Scan Detail    │  │  Queue Detail   │               │
│  │  (global room)  │  │ (scan_123 room) │  │(queue_456 room) │               │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘               │
│           │                    │                    │                         │
│           ▼                    ▼                    ▼                         │
│  ┌──────────────────────────────────────────────────────────────────┐        │
│  │                    pybirch-realtime.js                            │        │
│  │  WebSocket client with automatic reconnection & room management  │        │
│  └──────────────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Room-Based Scalability Model

### WebSocket Rooms

| Room Name | Purpose | Subscribers |
|-----------|---------|-------------|
| `(global)` | All status updates | Dashboard, list pages |
| `scan_{id}` | Specific scan updates + data | Scan detail page |
| `queue_{id}` | Specific queue updates + logs | Queue detail page |
| `instruments` | All instrument status | Instrument pages |
| `instrument_{id}` | Specific instrument position | Instrument detail |

### Why Rooms?

- **Efficiency**: Only relevant updates sent to interested clients
- **Scalability**: 1000 scans running = 1000 rooms, each isolated
- **Bandwidth**: Live data streaming only to scan_detail viewers
- **Flexibility**: User can watch specific scans without global noise

---

## Implementation Tasks

### Phase 1: JavaScript WebSocket Client (Core)

#### Task 1.1: Create `pybirch-realtime.js`

**Location**: `database/web/static/js/pybirch-realtime.js`

```javascript
// Core WebSocket client with:
// - Auto-reconnection with exponential backoff
// - Room subscription management
// - Event dispatcher pattern
// - Connection state handling
```

**Features**:
- `PyBirchRealtime` class
- Methods: `connect()`, `disconnect()`, `subscribe(room)`, `unsubscribe(room)`
- Event callbacks: `onScanStatus`, `onQueueStatus`, `onDataPoint`, `onInstrumentStatus`
- Auto-reconnect with 1s, 2s, 4s, 8s... backoff (max 30s)
- Connection status indicator support

#### Task 1.2: Add Socket.IO CDN to base.html

Add `<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>` to base template.

---

### Phase 2: Queue Real-Time Updates

#### Task 2.1: Update `queues.html` template

- Add connection indicator (green/red dot)
- Add live status badge updates
- Add progress bar animations
- Highlight rows when status changes

#### Task 2.2: Update `queue_detail.html` template

- Live progress bar
- Current scan indicator
- Real-time scan list status updates
- Live log panel (scrolling, color-coded by level)
- Queue controls (pause/resume) with instant feedback

#### Task 2.3: Create `QueueRealtimeManager` JS class

```javascript
class QueueRealtimeManager {
    constructor(queueId) { ... }
    updateProgress(completed, total) { ... }
    updateStatus(status) { ... }
    highlightCurrentScan(scanId) { ... }
    appendLog(level, message, timestamp) { ... }
}
```

---

### Phase 3: Scan Real-Time Updates

#### Task 3.1: Update `scans.html` template

- Live status badge updates
- Row highlighting on status change
- Auto-refresh of running scan count

#### Task 3.2: Update `scan_detail.html` template

- Live progress bar with percentage
- Real-time status updates
- **Live data chart** using Chart.js/Plotly
- Data point counter
- Elapsed time display

#### Task 3.3: Create `ScanRealtimeManager` JS class

```javascript
class ScanRealtimeManager {
    constructor(scanId, chartConfig) { ... }
    updateProgress(progress) { ... }
    updateStatus(status, message) { ... }
    addDataPoint(measurement, data) { ... }  // Live chart update
    updateElapsedTime() { ... }
}
```

#### Task 3.4: Live Chart Integration

- Initialize Chart.js scatter chart
- Buffer incoming data points (max 1000 visible)
- Smooth scrolling window for streaming data
- Axis auto-scaling with bounds

---

### Phase 4: Instrument Real-Time Updates

#### Task 4.1: Extend Instrument Model

Current fields: `id`, `name`, `status`, `specifications`, etc.

**Add live tracking fields** (broadcast only, not persisted every update):
- `live_status`: connected | disconnected | moving | measuring | error | idle
- `live_position`: `{axis: value, ...}` for movement instruments
- `live_value`: Current measurement value for sensors

#### Task 4.2: Update `instruments.html` template

- Connection status dots (🟢 connected, 🔴 disconnected, 🟡 busy)
- Live status column
- Position column for movement instruments (X: 1.234, Y: 5.678)

#### Task 4.3: Update `instrument_detail.html` template

- Large status indicator with animation
- Position display panel:
  ```
  ┌────────────────────────────┐
  │ Stage Position             │
  │ X: 12.345 mm  ◄───────────▶│
  │ Y: 67.890 mm  ◄───────────▶│
  │ Z:  0.500 mm  ◄───────────▶│
  │ Status: Moving to target   │
  └────────────────────────────┘
  ```
- Error display panel (red, dismissible)
- Current settings JSON viewer (collapsible)

#### Task 4.4: Create `InstrumentRealtimeManager` JS class

```javascript
class InstrumentRealtimeManager {
    constructor(instrumentId) { ... }
    updateStatus(status, error) { ... }
    updatePosition(axis, value) { ... }  // Animate position changes
    updateSettings(settings) { ... }
}
```

#### Task 4.5: Extend WebSocket Server for Position Updates

Add to `websocket_server.py`:

```python
def broadcast_instrument_position(
    self,
    instrument_id: int,
    instrument_name: str,
    position: Dict[str, float],  # {'x': 1.0, 'y': 2.0, 'z': 0.5}
    target_position: Optional[Dict[str, float]] = None,
    is_moving: bool = False
):
    """Broadcast instrument position for live tracking."""
```

#### Task 4.6: PyBirch Instrument Integration

Add position reporting to Movement instruments:

```python
# In movement instrument classes
def move_to(self, target):
    self._report_position_start(target)
    # ... perform move ...
    while moving:
        self._report_current_position()  # Broadcasts to WebSocket
    self._report_position_complete()
```

---

### Phase 5: Dashboard Integration

#### Task 5.1: Create Live Dashboard Widget

Add to `index.html`:

```html
<div class="live-activity-panel">
    <h3>🔴 Live Activity</h3>
    <div id="running-queues"></div>
    <div id="running-scans"></div>
    <div id="instrument-status-summary"></div>
</div>
```

#### Task 5.2: Dashboard JavaScript

- Subscribe to global events
- Show top 5 active queues with progress
- Show running scan count per queue
- Instrument status summary (3 connected, 1 error)

---

## File Structure

```
database/web/
├── static/
│   └── js/
│       ├── main.js                    # Existing
│       ├── pybirch-realtime.js        # NEW: Core WebSocket client
│       ├── scan-realtime.js           # NEW: Scan page handlers
│       ├── queue-realtime.js          # NEW: Queue page handlers
│       └── instrument-realtime.js     # NEW: Instrument page handlers
│
├── templates/
│   ├── base.html                      # MODIFY: Add Socket.IO CDN
│   ├── index.html                     # MODIFY: Add live dashboard panel
│   ├── scans.html                     # MODIFY: Add realtime updates
│   ├── scan_detail.html               # MODIFY: Add live chart, progress
│   ├── queues.html                    # MODIFY: Add realtime updates
│   ├── queue_detail.html              # MODIFY: Add live log, progress
│   ├── instruments.html               # MODIFY: Add status indicators
│   └── instrument_detail.html         # MODIFY: Add position panel
│
└── app.py                             # EXISTING: Already has SocketIO
```

---

## WebSocket Event Schema

### Client → Server

```javascript
// Subscribe to scan updates
socket.emit('subscribe_scan', { scan_id: 'SCAN_001' });

// Subscribe to queue updates  
socket.emit('subscribe_queue', { queue_id: 'QUEUE_001' });

// Subscribe to all instrument updates
socket.emit('subscribe_instruments');

// Subscribe to specific instrument position
socket.emit('subscribe_instrument', { instrument_id: 5 });
```

### Server → Client

```javascript
// Scan status (room: scan_{id} + global)
{
    event: 'scan_status',
    data: {
        scan_id: 'SCAN_001',
        status: 'running',
        progress: 0.45,
        message: 'Measuring point 45/100',
        timestamp: '2026-01-07T15:30:00Z'
    }
}

// Queue status (room: queue_{id} + global)
{
    event: 'queue_status',
    data: {
        queue_id: 'QUEUE_001',
        status: 'running',
        current_scan: 'SCAN_003',
        completed_scans: 2,
        total_scans: 10,
        timestamp: '2026-01-07T15:30:00Z'
    }
}

// Data point (room: scan_{id} only - NOT global)
{
    event: 'data_point',
    data: {
        scan_id: 'SCAN_001',
        measurement: 'spectrometer_0',
        data: { wavelength: 532.5, intensity: 1234.5 },
        sequence_index: 45,
        timestamp: '2026-01-07T15:30:00Z'
    }
}

// Instrument status (room: instruments + global)
{
    event: 'instrument_status',
    data: {
        instrument_id: 5,
        instrument_name: 'XY Stage',
        status: 'moving',
        position: { x: 12.345, y: 67.890 },
        target: { x: 15.000, y: 70.000 },
        timestamp: '2026-01-07T15:30:00Z'
    }
}

// Queue log (room: queue_{id} only)
{
    event: 'queue_log',
    data: {
        queue_id: 'QUEUE_001',
        level: 'INFO',
        message: 'Starting scan SCAN_003',
        scan_id: 'SCAN_003',
        timestamp: '2026-01-07T15:30:00Z'
    }
}
```

---

## CSS Additions

```css
/* Connection indicator */
.connection-status {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;
}
.connection-status.connected { background: #22c55e; }
.connection-status.disconnected { background: #ef4444; }
.connection-status.connecting { background: #f59e0b; animation: pulse 1s infinite; }

/* Status change highlight */
.status-updated {
    animation: highlight 2s ease-out;
}
@keyframes highlight {
    0% { background-color: rgba(59, 130, 246, 0.3); }
    100% { background-color: transparent; }
}

/* Live badge pulse */
.status-badge.status-running {
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}

/* Position display */
.position-panel {
    font-family: 'Courier New', monospace;
    background: #1e293b;
    color: #e2e8f0;
    padding: 16px;
    border-radius: 8px;
}
.position-axis {
    display: flex;
    justify-content: space-between;
    margin: 4px 0;
}
.position-value {
    color: #22d3ee;
    font-weight: bold;
}
.position-moving { color: #fbbf24; }
```

---

## Implementation Order

| Priority | Task | Estimated Time | Dependencies |
|----------|------|----------------|--------------|
| 1 | Task 1.1: Core JS Client | 2 hours | None |
| 2 | Task 1.2: Add Socket.IO CDN | 15 min | None |
| 3 | Task 2.1-2.3: Queue updates | 2 hours | Task 1 |
| 4 | Task 3.1-3.3: Scan updates | 2 hours | Task 1 |
| 5 | Task 3.4: Live chart | 2 hours | Task 3 |
| 6 | Task 4.1-4.4: Instrument UI | 3 hours | Task 1 |
| 7 | Task 4.5-4.6: Position tracking | 2 hours | Task 4 |
| 8 | Task 5.1-5.2: Dashboard | 1 hour | Tasks 2-4 |

**Total Estimated Time**: ~14 hours

---

## Testing Checklist

### Manual Testing

- [ ] Connect to WebSocket from browser console
- [ ] Subscribe to scan room, verify events received
- [ ] Subscribe to queue room, verify events received
- [ ] Start scan, verify progress updates in UI
- [ ] Verify live chart receives data points
- [ ] Test reconnection after server restart
- [ ] Test multiple browser tabs (same scan)
- [ ] Test with 10+ concurrent scans
- [ ] Verify instrument position updates

### Automated Testing

- [ ] Unit test JS client methods
- [ ] Integration test WebSocket server events
- [ ] Load test with simulated scans
- [ ] Memory leak test (long-running connection)

---

## Security Considerations

1. **Room validation**: Server should verify client can access requested room
2. **Rate limiting**: Limit subscription requests per client
3. **Data sanitization**: Escape HTML in log messages
4. **Authentication**: Use session cookie for WebSocket auth

---

## Future Enhancements

1. **Push notifications**: Browser notifications for scan complete/error
2. **Sound alerts**: Audio feedback for critical events
3. **Mobile app**: React Native client with same WebSocket
4. **Historical playback**: Replay scan execution from saved events
5. **Collaborative cursors**: See which scans other users are viewing
