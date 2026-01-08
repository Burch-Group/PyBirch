"""
WebSocket Server
================
Flask-SocketIO based WebSocket server for real-time PyBirch updates.

This module provides:
- ScanUpdateServer: Broadcasts scan/queue/data events to connected clients
- Integration with Flask app via SocketIO
- Room-based subscriptions for targeted updates
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import json

# Flask-SocketIO imports (optional dependency)
try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    SocketIO = None  # type: ignore
    emit = None  # type: ignore
    join_room = None  # type: ignore
    leave_room = None  # type: ignore

# Module-level SocketIO instance
_socketio: Optional[Any] = None


def get_socketio() -> Optional[Any]:
    """Get the global SocketIO instance."""
    return _socketio


def init_socketio(app: Any, **kwargs) -> Optional[Any]:
    """
    Initialize Flask-SocketIO with the Flask app.
    
    Args:
        app: Flask application instance
        **kwargs: Additional SocketIO configuration options
        
    Returns:
        SocketIO instance or None if flask-socketio not installed
    """
    global _socketio
    
    if not SOCKETIO_AVAILABLE:
        print("Warning: flask-socketio not installed. Real-time features disabled.")
        return None
    
    # Default configuration
    config = {
        'async_mode': 'threading',  # Compatible with standard Flask
        'cors_allowed_origins': '*',  # Allow all origins for development
        'ping_interval': 25,
        'ping_timeout': 120,
    }
    config.update(kwargs)
    
    _socketio = SocketIO(app, **config)
    return _socketio


class ScanUpdateServer:
    """
    WebSocket server for broadcasting real-time scan updates.
    
    This class manages WebSocket communications for:
    - Scan status changes (started, paused, completed, failed)
    - Queue state transitions
    - Live measurement data streaming
    - Instrument status updates
    
    Usage:
        from flask import Flask
        from flask_socketio import SocketIO
        from pybirch.database_integration.sync import ScanUpdateServer
        
        app = Flask(__name__)
        socketio = SocketIO(app)
        
        server = ScanUpdateServer(socketio)
        
        # Broadcast scan status
        server.broadcast_scan_status('SCAN_001', 'running', progress=0.5)
        
        # Broadcast data point
        server.broadcast_data_point('SCAN_001', 'voltage', {'x': 1.0, 'y': 2.5})
    """
    
    def __init__(self, socketio: Any):
        """
        Initialize the update server.
        
        Args:
            socketio: Flask-SocketIO instance
        """
        self.socketio = socketio
        self._registered = False
    
    def register_handlers(self):
        """Register WebSocket event handlers."""
        if self._registered or not self.socketio or not SOCKETIO_AVAILABLE:
            return
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            emit('connected', {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            pass
        
        @self.socketio.on('subscribe_scan')
        def handle_subscribe_scan(data):
            """Subscribe to updates for a specific scan."""
            scan_id = data.get('scan_id')
            if scan_id:
                join_room(f'scan_{scan_id}')
                emit('subscribed', {'scan_id': scan_id})
        
        @self.socketio.on('unsubscribe_scan')
        def handle_unsubscribe_scan(data):
            """Unsubscribe from scan updates."""
            scan_id = data.get('scan_id')
            if scan_id:
                leave_room(f'scan_{scan_id}')
        
        @self.socketio.on('subscribe_queue')
        def handle_subscribe_queue(data):
            """Subscribe to updates for a specific queue."""
            queue_id = data.get('queue_id')
            if queue_id:
                join_room(f'queue_{queue_id}')
                emit('subscribed', {'queue_id': queue_id})
        
        @self.socketio.on('unsubscribe_queue')
        def handle_unsubscribe_queue(data):
            """Unsubscribe from queue updates."""
            queue_id = data.get('queue_id')
            if queue_id:
                leave_room(f'queue_{queue_id}')
        
        @self.socketio.on('subscribe_instruments')
        def handle_subscribe_instruments():
            """Subscribe to instrument status updates."""
            join_room('instruments')
            emit('subscribed', {'room': 'instruments'})
        
        @self.socketio.on('unsubscribe_instruments')
        def handle_unsubscribe_instruments():
            """Unsubscribe from instrument updates."""
            leave_room('instruments')
        
        @self.socketio.on('subscribe_instrument')
        def handle_subscribe_instrument(data):
            """Subscribe to a specific instrument's position updates."""
            instrument_id = data.get('instrument_id')
            if instrument_id:
                join_room(f'instrument_{instrument_id}')
                emit('subscribed', {'instrument_id': instrument_id})
        
        @self.socketio.on('unsubscribe_instrument')
        def handle_unsubscribe_instrument(data):
            """Unsubscribe from a specific instrument."""
            instrument_id = data.get('instrument_id')
            if instrument_id:
                leave_room(f'instrument_{instrument_id}')
        
        @self.socketio.on('subscribe_queues')
        def handle_subscribe_queues():
            """Subscribe to all queue status updates (global dashboard)."""
            join_room('all_queues')
            emit('subscribed', {'room': 'all_queues'})
        
        @self.socketio.on('unsubscribe_queues')
        def handle_unsubscribe_queues():
            """Unsubscribe from all queue updates."""
            leave_room('all_queues')
        
        @self.socketio.on('subscribe_scans')
        def handle_subscribe_scans():
            """Subscribe to all scan status updates (global dashboard)."""
            join_room('all_scans')
            emit('subscribed', {'room': 'all_scans'})
        
        @self.socketio.on('unsubscribe_scans')
        def handle_unsubscribe_scans():
            """Unsubscribe from all scan updates."""
            leave_room('all_scans')
        
        self._registered = True
    
    def broadcast_scan_status(
        self,
        scan_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        Broadcast scan status update to all subscribed clients.
        
        Args:
            scan_id: Unique scan identifier
            status: New scan status (queued, running, paused, completed, aborted, failed)
            progress: Optional progress percentage (0.0 - 1.0)
            message: Optional status message
            extra_data: Optional additional data
        """
        if not self.socketio:
            return
        
        payload: Dict[str, Any] = {
            'scan_id': scan_id,
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if progress is not None:
            payload['progress'] = progress
        if message:
            payload['message'] = message
        if extra_data:
            payload['extra'] = extra_data
        
        # Broadcast to scan-specific room and global rooms
        self.socketio.emit('scan_status', payload, room=f'scan_{scan_id}')
        self.socketio.emit('scan_status', payload, room='all_scans')  # Dashboard subscribers
    
    def broadcast_queue_status(
        self,
        queue_id: str,
        status: str,
        current_scan: Optional[str] = None,
        completed_scans: Optional[int] = None,
        total_scans: Optional[int] = None,
        message: Optional[str] = None
    ):
        """
        Broadcast queue status update to all subscribed clients.
        
        Args:
            queue_id: Unique queue identifier
            status: New queue status (idle, running, paused, stopping, completed)
            current_scan: Currently executing scan ID
            completed_scans: Number of completed scans
            total_scans: Total number of scans in queue
            message: Optional status message
        """
        if not self.socketio:
            return
        
        payload: Dict[str, Any] = {
            'queue_id': queue_id,
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if current_scan:
            payload['current_scan'] = current_scan
        if completed_scans is not None:
            payload['completed_scans'] = completed_scans
        if total_scans is not None:
            payload['total_scans'] = total_scans
        if message:
            payload['message'] = message
        
        # Broadcast to queue-specific room and global rooms
        self.socketio.emit('queue_status', payload, room=f'queue_{queue_id}')
        self.socketio.emit('queue_status', payload, room='all_queues')  # Dashboard subscribers
    
    def broadcast_data_point(
        self,
        scan_id: str,
        measurement_name: str,
        data: Dict[str, Any],
        sequence_index: Optional[int] = None
    ):
        """
        Broadcast new measurement data point for live plotting.
        
        Args:
            scan_id: Scan that generated the data
            measurement_name: Name of the measurement object
            data: Dictionary of column values
            sequence_index: Optional sequence index of the data point
        """
        if not self.socketio:
            return
        
        payload = {
            'scan_id': scan_id,
            'measurement': measurement_name,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if sequence_index is not None:
            payload['sequence_index'] = sequence_index
        
        self.socketio.emit('data_point', payload, room=f'scan_{scan_id}')
    
    def broadcast_instrument_status(
        self,
        instrument_id: int,
        instrument_name: str,
        status: str,
        error_message: Optional[str] = None,
        current_settings: Optional[Dict[str, Any]] = None
    ):
        """
        Broadcast instrument status update.
        
        Args:
            instrument_id: Database ID of the instrument
            instrument_name: Human-readable instrument name
            status: Connection status (connected, disconnected, error, busy)
            error_message: Error details if status is 'error'
            current_settings: Current instrument settings if connected
        """
        if not self.socketio:
            return
        
        payload = {
            'instrument_id': instrument_id,
            'instrument_name': instrument_name,
            'status': status,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if error_message:
            payload['error'] = error_message
        if current_settings:
            payload['settings'] = current_settings
        
        self.socketio.emit('instrument_status', payload, room='instruments')
        self.socketio.emit('instrument_status', payload)
    
    def broadcast_instrument_position(
        self,
        instrument_id: int,
        instrument_name: str,
        position: Dict[str, float],
        target_position: Optional[Dict[str, float]] = None,
        is_moving: bool = False,
        status: Optional[str] = None
    ):
        """
        Broadcast instrument position update for live tracking.
        
        Args:
            instrument_id: Database ID of the instrument
            instrument_name: Human-readable instrument name
            position: Current position as dict (e.g., {'x': 1.0, 'y': 2.0, 'z': 0.5})
            target_position: Target position if moving
            is_moving: Whether the instrument is currently moving
            status: Optional status (idle, moving, homing, error)
        """
        if not self.socketio:
            return
        
        payload: Dict[str, Any] = {
            'instrument_id': instrument_id,
            'instrument_name': instrument_name,
            'position': position,
            'is_moving': is_moving,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if target_position:
            payload['target'] = target_position
        if status:
            payload['status'] = status
        
        # Send to instrument-specific room and general instruments room
        self.socketio.emit('instrument_position', payload, room=f'instrument_{instrument_id}')
        self.socketio.emit('instrument_position', payload, room='instruments')
    
    def broadcast_log_entry(
        self,
        queue_id: str,
        level: str,
        message: str,
        scan_id: Optional[str] = None
    ):
        """
        Broadcast log entry from queue execution.
        
        Args:
            queue_id: Queue that generated the log
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            message: Log message
            scan_id: Associated scan ID if applicable
        """
        if not self.socketio:
            return
        
        payload = {
            'queue_id': queue_id,
            'level': level,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if scan_id:
            payload['scan_id'] = scan_id
        
        self.socketio.emit('queue_log', payload, room=f'queue_{queue_id}')
    
    # Alias for broadcast_log_entry for consistency
    broadcast_queue_log = broadcast_log_entry
