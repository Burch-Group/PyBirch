"""
WebSocket Integration
=====================
Bridge module that connects PyBirch Queue/Scan execution to WebSocket broadcasts.

This module provides:
- WebSocketQueueBridge: Connects Queue callbacks to WebSocket broadcasts
- WebSocketScanExtension: ScanExtension that broadcasts events
- WebSocketClient: Client that connects to a remote WebSocket server
- setup_websocket_integration: Helper to wire everything together

Usage:
    from pybirch.database_integration.sync import setup_websocket_integration
    
    # With an existing ScanUpdateServer (from Flask-SocketIO app)
    bridge = setup_websocket_integration(queue, update_server)
    
    # Or connect to a remote WebSocket server (for cross-process communication)
    bridge = setup_websocket_integration(queue, server_url="http://localhost:5000")
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, TYPE_CHECKING, Callable
import logging
import threading
import json
import time

if TYPE_CHECKING:
    from pybirch.queue.queue import Queue, ScanState, LogEntry
    from pybirch.scan.scan import Scan
    from .websocket_server import ScanUpdateServer

logger = logging.getLogger(__name__)


class WebSocketClient:
    """
    WebSocket client that connects to a remote Flask-SocketIO server.
    
    This client implements the same interface as ScanUpdateServer, allowing
    it to be used interchangeably with the bridge classes. Events are sent
    to the server which then broadcasts them to connected web clients.
    
    This enables cross-process communication when the GUI and web server
    run as separate processes.
    
    Usage:
        client = WebSocketClient(server_url="http://localhost:5000")
        client.connect()
        
        # Use like ScanUpdateServer
        client.broadcast_scan_status(scan_id="scan_001", status="running", progress=0.5)
    """
    
    def __init__(self, server_url: str = "http://localhost:5000"):
        """
        Initialize the WebSocket client.
        
        Args:
            server_url: URL of the Flask-SocketIO server
        """
        self.server_url = server_url.rstrip('/')
        self._sio = None
        self._connected = False
        self._connect_lock = threading.Lock()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._callbacks: Dict[str, List[Callable]] = {}
        
    def connect(self) -> bool:
        """
        Connect to the WebSocket server.
        
        Returns:
            True if connected successfully, False otherwise
        """
        with self._connect_lock:
            if self._connected:
                return True
            
            try:
                import socketio
                
                self._sio = socketio.Client(
                    logger=False,
                    engineio_logger=False,
                    reconnection=True,
                    reconnection_attempts=self._max_reconnect_attempts,
                    reconnection_delay=1,
                    reconnection_delay_max=5,
                )
                
                @self._sio.event
                def connect():
                    self._connected = True
                    self._reconnect_attempts = 0
                    logger.info(f"[WS Client] Connected to {self.server_url}")
                    self._emit_callbacks('connected', {})
                
                @self._sio.event
                def disconnect():
                    self._connected = False
                    logger.info("[WS Client] Disconnected from server")
                    self._emit_callbacks('disconnected', {})
                
                @self._sio.event
                def connect_error(data):
                    logger.warning(f"[WS Client] Connection error: {data}")
                    self._emit_callbacks('error', {'error': str(data)})
                
                # Connect to the server
                self._sio.connect(
                    self.server_url,
                    namespaces=['/'],
                    wait=True,
                    wait_timeout=5
                )
                
                return self._connected
                
            except ImportError:
                logger.error("python-socketio not installed. Run: pip install python-socketio[client]")
                return False
            except Exception as e:
                logger.error(f"[WS Client] Failed to connect: {e}")
                self._connected = False
                return False
    
    def disconnect(self):
        """Disconnect from the WebSocket server."""
        with self._connect_lock:
            if self._sio and self._connected:
                try:
                    self._sio.disconnect()
                except Exception as e:
                    logger.warning(f"[WS Client] Error during disconnect: {e}")
                finally:
                    self._connected = False
                    self._sio = None
    
    def is_connected(self) -> bool:
        """Check if connected to the server."""
        return self._connected and self._sio is not None
    
    def add_callback(self, event: str, callback: Callable):
        """Add a callback for an event."""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)
    
    def remove_callback(self, event: str, callback: Callable):
        """Remove a callback for an event."""
        if event in self._callbacks:
            try:
                self._callbacks[event].remove(callback)
            except ValueError:
                pass
    
    def _emit_callbacks(self, event: str, data: Dict[str, Any]):
        """Emit callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"[WS Client] Callback error: {e}")
    
    def _emit(self, event: str, data: Dict[str, Any]):
        """
        Emit an event to the server.
        
        Args:
            event: Event name
            data: Event data
        """
        if not self.is_connected():
            logger.warning(f"[WS Client] Not connected, cannot emit {event}")
            return
        
        try:
            self._sio.emit(event, data)
        except Exception as e:
            logger.warning(f"[WS Client] Failed to emit {event}: {e}")
    
    def broadcast_scan_status(
        self,
        scan_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        Send a scan status update to the server.
        
        Args:
            scan_id: Unique scan identifier
            status: Status string (queued, running, paused, completed, aborted, failed)
            progress: Progress value 0.0-1.0
            message: Optional status message
            extra_data: Additional data to include
        """
        data = {
            'scan_id': scan_id,
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        }
        if progress is not None:
            data['progress'] = progress
        if message:
            data['message'] = message
        if extra_data:
            data.update(extra_data)
        
        self._emit('client_scan_status', data)
    
    def broadcast_queue_status(
        self,
        queue_id: str,
        status: str,
        total_scans: Optional[int] = None,
        completed_scans: Optional[int] = None,
        current_scan: Optional[str] = None,
        message: Optional[str] = None
    ):
        """
        Send a queue status update to the server.
        
        Args:
            queue_id: Queue identifier
            status: Queue status (idle, running, paused, completed, stopped)
            total_scans: Total number of scans in queue
            completed_scans: Number of completed scans
            current_scan: ID of currently running scan
            message: Optional status message
        """
        data = {
            'queue_id': queue_id,
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        }
        if total_scans is not None:
            data['total_scans'] = total_scans
        if completed_scans is not None:
            data['completed_scans'] = completed_scans
        if current_scan:
            data['current_scan'] = current_scan
        if message:
            data['message'] = message
        
        self._emit('client_queue_status', data)
    
    def broadcast_data_point(
        self,
        scan_id: str,
        measurement_name: str,
        data: Dict[str, Any],
        sequence_index: Optional[int] = None
    ):
        """
        Send a data point to the server for broadcast.
        
        Args:
            scan_id: Scan identifier
            measurement_name: Name of the measurement
            data: Data point dictionary
            sequence_index: Optional sequence number
        """
        payload = {
            'scan_id': scan_id,
            'measurement_name': measurement_name,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        if sequence_index is not None:
            payload['sequence_index'] = sequence_index
        
        self._emit('client_data_point', payload)
    
    def broadcast_log_entry(
        self,
        queue_id: str,
        level: str,
        message: str,
        scan_id: Optional[str] = None
    ):
        """
        Send a log entry to the server.
        
        Args:
            queue_id: Queue identifier
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Log message
            scan_id: Optional scan identifier
        """
        data = {
            'queue_id': queue_id,
            'level': level,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        if scan_id:
            data['scan_id'] = scan_id
        
        self._emit('client_log_entry', data)
    
    def __del__(self):
        """Clean up on deletion."""
        self.disconnect()


def check_server_running(server_url: str = "http://localhost:5000", timeout: float = 2.0) -> bool:
    """
    Check if the WebSocket server is running.
    
    Args:
        server_url: URL of the server to check
        timeout: Request timeout in seconds
        
    Returns:
        True if server is responding, False otherwise
    """
    import urllib.request
    import urllib.error
    
    try:
        url = f"{server_url.rstrip('/')}/health"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass
    
    # Try the root endpoint
    try:
        url = server_url.rstrip('/')
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass
    
    return False


class WebSocketQueueBridge:
    """
    Bridge that connects Queue callbacks to WebSocket broadcasts.
    
    This class registers itself with a Queue's callback system and
    forwards events to the ScanUpdateServer for WebSocket broadcast.
    
    Usage:
        from pybirch.queue.queue import Queue
        from pybirch.database_integration.sync import ScanUpdateServer, WebSocketQueueBridge
        
        queue = Queue(QID="test")
        server = ScanUpdateServer(socketio)
        
        bridge = WebSocketQueueBridge(queue, server)
        # Now all queue events will be broadcast via WebSocket
    """
    
    def __init__(
        self,
        queue: 'Queue',
        update_server: 'ScanUpdateServer',
        queue_id: Optional[str] = None,
    ):
        """
        Initialize the WebSocket bridge.
        
        Args:
            queue: PyBirch Queue instance to monitor
            update_server: ScanUpdateServer for broadcasting
            queue_id: Optional custom queue ID for broadcasts (defaults to queue.QID)
        """
        self.queue = queue
        self.server = update_server
        self.queue_id = queue_id or queue.QID
        
        # Track queue state
        self._is_running = False
        self._completed_scans = 0
        
        # Register callbacks
        self._register_callbacks()
        
        logger.info(f"WebSocket bridge initialized for queue {self.queue_id}")
    
    def _register_callbacks(self):
        """Register callbacks with the queue."""
        self.queue.add_log_callback(self._on_log_entry)
        self.queue.add_state_callback(self._on_state_change)
        self.queue.add_progress_callback(self._on_progress_update)
    
    def unregister(self):
        """Unregister callbacks from the queue."""
        try:
            self.queue.remove_log_callback(self._on_log_entry)
            self.queue.remove_state_callback(self._on_state_change)
            self.queue.remove_progress_callback(self._on_progress_update)
        except (ValueError, AttributeError):
            pass  # Callback not registered
    
    def _on_log_entry(self, entry: 'LogEntry'):
        """Forward log entries to WebSocket broadcast."""
        try:
            self.server.broadcast_log_entry(
                queue_id=self.queue_id,
                level=entry.level,
                message=entry.message,
                scan_id=entry.scan_id
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast log entry: {e}")
    
    def _on_state_change(self, scan_id: str, state: 'ScanState'):
        """Forward scan state changes to WebSocket broadcast."""
        try:
            # Import here to avoid circular imports
            from pybirch.queue.queue import ScanState, QueueState
            
            # Get scan handle for additional info
            handle = None
            try:
                for h in self.queue._scan_handles:
                    if h.scan_id == scan_id:
                        handle = h
                        break
            except:
                pass
            
            scan_name = None
            if handle and handle.scan:
                scan_name = getattr(handle.scan.scan_settings, 'scan_name', None)
            
            # Broadcast scan status
            status_map = {
                ScanState.QUEUED: 'queued',
                ScanState.RUNNING: 'running',
                ScanState.PAUSED: 'paused',
                ScanState.COMPLETED: 'completed',
                ScanState.ABORTED: 'aborted',
                ScanState.FAILED: 'failed',
            }
            
            status = status_map.get(state, state.name.lower())
            progress = handle.progress if handle else 0.0
            
            self.server.broadcast_scan_status(
                scan_id=scan_id,
                status=status,
                progress=progress,
                message=f"Scan {scan_name or scan_id} {status}",
                extra_data={'queue_id': self.queue_id, 'name': scan_name}
            )
            
            # Track completed scans and broadcast queue status
            if state in (ScanState.COMPLETED, ScanState.ABORTED, ScanState.FAILED):
                self._completed_scans += 1
                self._broadcast_queue_status()
            
            # Broadcast queue start when first scan starts running
            if state == ScanState.RUNNING and not self._is_running:
                self._is_running = True
                self._completed_scans = 0
                self.server.broadcast_queue_status(
                    queue_id=self.queue_id,
                    status='running',
                    total_scans=self.queue.size(),
                    completed_scans=0,
                    current_scan=scan_id,
                    message="Queue started"
                )
            
            # Check if queue is complete
            if self._is_running:
                total = self.queue.size()
                if self._completed_scans >= total:
                    self._is_running = False
                    self.server.broadcast_queue_status(
                        queue_id=self.queue_id,
                        status='completed',
                        total_scans=total,
                        completed_scans=self._completed_scans,
                        message="Queue completed"
                    )
            
        except Exception as e:
            logger.warning(f"Failed to broadcast state change: {e}")
    
    def _on_progress_update(self, scan_id: str, progress: float):
        """Forward progress updates to WebSocket broadcast."""
        try:
            self.server.broadcast_scan_status(
                scan_id=scan_id,
                status='running',
                progress=progress
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast progress: {e}")
    
    def _broadcast_queue_status(self):
        """Broadcast current queue status."""
        try:
            # Determine current scan
            current_scan = None
            from pybirch.queue.queue import ScanState
            for h in self.queue._scan_handles:
                if h.state == ScanState.RUNNING:
                    current_scan = h.scan_id
                    break
            
            self.server.broadcast_queue_status(
                queue_id=self.queue_id,
                status='running' if self._is_running else 'idle',
                total_scans=self.queue.size(),
                completed_scans=self._completed_scans,
                current_scan=current_scan
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast queue status: {e}")
    
    def broadcast_queue_pause(self):
        """Broadcast queue pause event."""
        self.server.broadcast_queue_status(
            queue_id=self.queue_id,
            status='paused',
            message="Queue paused"
        )
    
    def broadcast_queue_resume(self):
        """Broadcast queue resume event."""
        self.server.broadcast_queue_status(
            queue_id=self.queue_id,
            status='running',
            message="Queue resumed"
        )
    
    def broadcast_queue_stop(self, reason: Optional[str] = None):
        """Broadcast queue stop event."""
        self._is_running = False
        self.server.broadcast_queue_status(
            queue_id=self.queue_id,
            status='stopped',
            message=reason or "Queue stopped"
        )


class WebSocketScanExtension:
    """
    ScanExtension that broadcasts scan events via WebSocket.
    
    This extension implements the ScanExtension interface and can be added 
    to scans to broadcast lifecycle events and data points in real-time.
    
    It follows the ScanExtension protocol:
    - startup(): Broadcast scan started
    - execute(): Broadcast scan executing
    - save_data(): Broadcast data points
    - shutdown(): Broadcast scan completed/stopped
    
    Usage:
        from pybirch.scan.scan import Scan
        from pybirch.database_integration.sync import WebSocketScanExtension
        
        ext = WebSocketScanExtension(update_server, scan_id="SCAN_001")
        scan.scan_settings.extensions.append(ext)
    """
    
    def __init__(
        self,
        update_server: 'ScanUpdateServer',
        scan_id: Optional[str] = None,
        scan_name: Optional[str] = None,
        queue_id: Optional[str] = None,
        broadcast_data_points: bool = True,
        data_point_interval: int = 1,  # Broadcast every N data points
    ):
        """
        Initialize WebSocket scan extension.
        
        Args:
            update_server: ScanUpdateServer for broadcasting
            scan_id: Scan ID for broadcasts (will be set by scan if not provided)
            scan_name: Human-readable scan name
            queue_id: Optional queue ID if scan is part of a queue
            broadcast_data_points: Whether to broadcast individual data points
            data_point_interval: Broadcast every N data points (1 = all)
        """
        # Note: We don't call super().__init__() because ScanExtension raises NotImplementedError
        self.server = update_server
        self.scan_id = scan_id
        self.scan_name = scan_name
        self.queue_id = queue_id
        self.broadcast_data_points = broadcast_data_points
        self.data_point_interval = max(1, data_point_interval)
        
        # Tracking
        self._data_point_count = 0
        self._start_time: Optional[datetime] = None
        self._scan_ref: Optional['Scan'] = None
        self._completed = False
    
    def set_scan_reference(self, scan: 'Scan'):
        """
        Called by Scan.startup() to set a reference to the parent scan.
        
        Args:
            scan: The PyBirch Scan object
        """
        self._scan_ref = scan
        if not self.scan_id:
            self.scan_id = getattr(scan.scan_settings, 'scan_id', None) or str(id(scan))
        if not self.scan_name:
            self.scan_name = getattr(scan.scan_settings, 'scan_name', None)
    
    def startup(self):
        """Called when the scan is starting up (by Scan.startup())."""
        self._start_time = datetime.utcnow()
        self._data_point_count = 0
        self._completed = False
        
        # Get scan details from reference if available
        if self._scan_ref and not self.scan_id:
            self.scan_id = getattr(self._scan_ref.scan_settings, 'scan_id', None) or str(id(self._scan_ref))
        if self._scan_ref and not self.scan_name:
            self.scan_name = getattr(self._scan_ref.scan_settings, 'scan_name', None)
        
        logger.info(f"[WS] Scan startup: {self.scan_id}")
    
    def execute(self):
        """Called when scan execution begins (by Scan.execute())."""
        self.server.broadcast_scan_status(
            scan_id=self.scan_id,
            status='running',
            progress=0.0,
            message=f"Scan {self.scan_name or self.scan_id} started",
            extra_data={'queue_id': self.queue_id} if self.queue_id else None
        )
        logger.info(f"[WS] Scan execute: {self.scan_id}")
    
    def save_data(self, data, measurement_name: str):
        """
        Called by Scan._save_data_async() for each measurement batch.
        Broadcasts data points via WebSocket.
        
        Args:
            data: DataFrame or dict containing measurement data
            measurement_name: Name/ID of the measurement
        """
        if self._completed:
            return
        
        import pandas as pd
        
        # Count data points
        if isinstance(data, pd.DataFrame):
            point_count = len(data)
        elif isinstance(data, dict):
            point_count = 1
        else:
            point_count = 1
        
        self._data_point_count += point_count
        
        # Broadcast if enabled and interval matches
        if self.broadcast_data_points:
            if self._data_point_count % self.data_point_interval == 0:
                # Convert DataFrame to dict for broadcasting
                if isinstance(data, pd.DataFrame) and len(data) > 0:
                    # Broadcast the last row
                    last_row = data.iloc[-1].to_dict()
                    self.server.broadcast_data_point(
                        scan_id=self.scan_id,
                        measurement_name=measurement_name,
                        data=last_row,
                        sequence_index=self._data_point_count
                    )
                elif isinstance(data, dict):
                    self.server.broadcast_data_point(
                        scan_id=self.scan_id,
                        measurement_name=measurement_name,
                        data=data,
                        sequence_index=self._data_point_count
                    )
    
    def shutdown(self):
        """Called when the scan is shutting down."""
        if self._completed:
            return
        
        self._completed = True
        
        duration = None
        if self._start_time:
            duration = (datetime.utcnow() - self._start_time).total_seconds()
        
        self.server.broadcast_scan_status(
            scan_id=self.scan_id,
            status='completed',
            progress=1.0,
            message=f"Scan {self.scan_name or self.scan_id} completed",
            extra_data={
                'duration_seconds': duration,
                'data_points': self._data_point_count,
                'queue_id': self.queue_id
            } if duration else None
        )
        logger.info(f"[WS] Scan shutdown: {self.scan_id} ({self._data_point_count} data points)")
    
    def on_complete(self):
        """Called when scan completes successfully (manual call)."""
        self.shutdown()
    
    def on_abort(self):
        """Called when scan is aborted."""
        self._completed = True
        self.server.broadcast_scan_status(
            scan_id=self.scan_id,
            status='aborted',
            message=f"Scan {self.scan_name or self.scan_id} aborted"
        )
    
    def on_pause(self):
        """Called when scan is paused."""
        self.server.broadcast_scan_status(
            scan_id=self.scan_id,
            status='paused',
            message="Scan paused"
        )
    
    def on_resume(self):
        """Called when scan resumes."""
        self.server.broadcast_scan_status(
            scan_id=self.scan_id,
            status='running',
            message="Scan resumed"
        )
    
    def on_progress(self, progress: float):
        """Called for progress updates."""
        self.server.broadcast_scan_status(
            scan_id=self.scan_id,
            status='running',
            progress=progress
        )
    
    def on_data_point(self, measurement_name: str, data: Dict[str, Any]):
        """Called for each data point collected (alternative to save_data)."""
        self._data_point_count += 1
        
        if self.broadcast_data_points:
            if self._data_point_count % self.data_point_interval == 0:
                self.server.broadcast_data_point(
                    scan_id=self.scan_id,
                    measurement_name=measurement_name,
                    data=data,
                    sequence_index=self._data_point_count
                )
    
    def on_error(self, error: Exception):
        """Called when scan encounters an error."""
        import traceback
        tb = traceback.format_exc()
        
        self.server.broadcast_scan_status(
            scan_id=self.scan_id,
            status='failed',
            message=f"Scan failed: {str(error)}",
            extra_data={'traceback': tb}
        )


def setup_websocket_integration(
    queue: 'Queue',
    update_server: Optional['ScanUpdateServer'] = None,
    server_url: Optional[str] = None,
    queue_id: Optional[str] = None,
    add_scan_extensions: bool = True,
    data_point_interval: int = 1,
) -> WebSocketQueueBridge:
    """
    Setup WebSocket integration for a queue.
    
    This function creates a WebSocketQueueBridge to forward queue events
    to the WebSocket server for real-time updates.
    
    Args:
        queue: PyBirch Queue to integrate
        update_server: ScanUpdateServer instance (required if server_url not provided)
        server_url: URL of WebSocket server to connect to (alternative to update_server)
        queue_id: Custom queue ID for broadcasts
        add_scan_extensions: Whether to add WebSocketScanExtension to enqueued scans
        data_point_interval: Broadcast every N data points
        
    Returns:
        WebSocketQueueBridge instance
        
    Raises:
        ValueError: If neither update_server nor server_url provided
        ConnectionError: If cannot connect to server_url
    """
    if update_server is None and server_url is None:
        raise ValueError("Either update_server or server_url must be provided")
    
    if update_server is None and server_url:
        # Check if server is running first
        if not check_server_running(server_url):
            raise ConnectionError(
                f"Cannot connect to WebSocket server at {server_url}. "
                "Make sure the web server is running."
            )
        
        # Create a WebSocket client to connect to the remote server
        client = WebSocketClient(server_url)
        if not client.connect():
            raise ConnectionError(
                f"Failed to establish WebSocket connection to {server_url}"
            )
        
        # Use the client as the update server (implements same interface)
        update_server = client
        logger.info(f"Connected to WebSocket server at {server_url}")
    
    # Create the bridge
    bridge = WebSocketQueueBridge(
        queue=queue,
        update_server=update_server,
        queue_id=queue_id
    )
    
    logger.info(f"WebSocket integration setup for queue {queue.QID}")
    
    return bridge


def create_websocket_scan_extension(
    update_server: 'ScanUpdateServer',
    scan_id: Optional[str] = None,
    scan_name: Optional[str] = None,
    queue_id: Optional[str] = None,
    broadcast_data_points: bool = True,
    data_point_interval: int = 1,
) -> WebSocketScanExtension:
    """
    Create a WebSocket scan extension for real-time updates.
    
    Args:
        update_server: ScanUpdateServer for broadcasting
        scan_id: Scan ID for broadcasts
        scan_name: Human-readable scan name
        queue_id: Optional queue ID if scan is part of a queue
        broadcast_data_points: Whether to broadcast individual data points
        data_point_interval: Broadcast every N data points
        
    Returns:
        Configured WebSocketScanExtension
    """
    return WebSocketScanExtension(
        update_server=update_server,
        scan_id=scan_id,
        scan_name=scan_name,
        queue_id=queue_id,
        broadcast_data_points=broadcast_data_points,
        data_point_interval=data_point_interval
    )
