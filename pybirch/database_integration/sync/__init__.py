"""
Sync Module
===========
Real-time synchronization components for PyBirch database integration.

This module provides WebSocket-based real-time updates for:
- Scan status changes
- Queue state transitions
- Measurement data streaming
- Instrument status updates
"""

from .websocket_server import ScanUpdateServer, get_socketio
from .event_handlers import (
    register_scan_events,
    register_queue_events,
    register_instrument_events,
)
from .websocket_integration import (
    WebSocketQueueBridge,
    WebSocketScanExtension,
    WebSocketClient,
    setup_websocket_integration,
    create_websocket_scan_extension,
    check_server_running,
)

__all__ = [
    'ScanUpdateServer',
    'get_socketio',
    'register_scan_events',
    'register_queue_events',
    'register_instrument_events',
    'WebSocketQueueBridge',
    'WebSocketScanExtension',
    'WebSocketClient',
    'setup_websocket_integration',
    'create_websocket_scan_extension',
    'check_server_running',
]
