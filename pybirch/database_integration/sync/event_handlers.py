"""
Event Handlers
==============
Event handlers that bridge PyBirch scan/queue events to WebSocket broadcasts.

These handlers are registered with PyBirch components to automatically
broadcast state changes to connected WebSocket clients.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Callable, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .websocket_server import ScanUpdateServer

logger = logging.getLogger(__name__)


class ScanEventHandler:
    """
    Handles scan lifecycle events and broadcasts to WebSocket clients.
    
    This handler can be attached to PyBirch scans via callbacks or
    used with DatabaseExtension to automatically broadcast updates.
    """
    
    def __init__(self, update_server: 'ScanUpdateServer'):
        """
        Initialize the scan event handler.
        
        Args:
            update_server: ScanUpdateServer instance for broadcasting
        """
        self.server = update_server
    
    def on_scan_start(self, scan_id: str, scan_name: Optional[str] = None):
        """Handle scan start event."""
        self.server.broadcast_scan_status(
            scan_id=scan_id,
            status='running',
            progress=0.0,
            message=f"Scan {scan_name or scan_id} started"
        )
    
    def on_scan_progress(self, scan_id: str, progress: float, message: Optional[str] = None):
        """Handle scan progress update."""
        self.server.broadcast_scan_status(
            scan_id=scan_id,
            status='running',
            progress=progress,
            message=message
        )
    
    def on_scan_pause(self, scan_id: str):
        """Handle scan pause event."""
        self.server.broadcast_scan_status(
            scan_id=scan_id,
            status='paused',
            message="Scan paused"
        )
    
    def on_scan_resume(self, scan_id: str):
        """Handle scan resume event."""
        self.server.broadcast_scan_status(
            scan_id=scan_id,
            status='running',
            message="Scan resumed"
        )
    
    def on_scan_complete(self, scan_id: str, duration_seconds: Optional[float] = None):
        """Handle scan completion event."""
        extra: Dict[str, Any] = {}
        if duration_seconds is not None:
            extra['duration_seconds'] = duration_seconds
        
        self.server.broadcast_scan_status(
            scan_id=scan_id,
            status='completed',
            progress=1.0,
            message="Scan completed successfully",
            extra_data=extra if extra else None
        )
    
    def on_scan_abort(self, scan_id: str, reason: Optional[str] = None):
        """Handle scan abort event."""
        self.server.broadcast_scan_status(
            scan_id=scan_id,
            status='aborted',
            message=reason or "Scan aborted by user"
        )
    
    def on_scan_error(self, scan_id: str, error: str, traceback: Optional[str] = None):
        """Handle scan error event."""
        extra: Dict[str, Any] = {}
        if traceback:
            extra['traceback'] = traceback
        
        self.server.broadcast_scan_status(
            scan_id=scan_id,
            status='failed',
            message=f"Scan failed: {error}",
            extra_data=extra if extra else None
        )
    
    def on_data_point(
        self,
        scan_id: str,
        measurement_name: str,
        values: Dict[str, Any],
        index: Optional[int] = None
    ):
        """Handle new data point event."""
        self.server.broadcast_data_point(
            scan_id=scan_id,
            measurement_name=measurement_name,
            data=values,
            sequence_index=index
        )


class QueueEventHandler:
    """
    Handles queue lifecycle events and broadcasts to WebSocket clients.
    
    This handler can be used with DatabaseQueue to automatically
    broadcast queue state changes.
    """
    
    def __init__(self, update_server: 'ScanUpdateServer'):
        """
        Initialize the queue event handler.
        
        Args:
            update_server: ScanUpdateServer instance for broadcasting
        """
        self.server = update_server
    
    def on_queue_start(self, queue_id: str, total_scans: int):
        """Handle queue start event."""
        self.server.broadcast_queue_status(
            queue_id=queue_id,
            status='running',
            total_scans=total_scans,
            completed_scans=0,
            message="Queue execution started"
        )
    
    def on_queue_progress(
        self,
        queue_id: str,
        completed_scans: int,
        total_scans: int,
        current_scan: Optional[str] = None
    ):
        """Handle queue progress update."""
        self.server.broadcast_queue_status(
            queue_id=queue_id,
            status='running',
            current_scan=current_scan,
            completed_scans=completed_scans,
            total_scans=total_scans
        )
    
    def on_queue_pause(self, queue_id: str):
        """Handle queue pause event."""
        self.server.broadcast_queue_status(
            queue_id=queue_id,
            status='paused',
            message="Queue paused"
        )
    
    def on_queue_resume(self, queue_id: str):
        """Handle queue resume event."""
        self.server.broadcast_queue_status(
            queue_id=queue_id,
            status='running',
            message="Queue resumed"
        )
    
    def on_queue_complete(self, queue_id: str, completed_scans: int, total_scans: int):
        """Handle queue completion event."""
        self.server.broadcast_queue_status(
            queue_id=queue_id,
            status='completed',
            completed_scans=completed_scans,
            total_scans=total_scans,
            message="Queue completed"
        )
    
    def on_queue_stop(self, queue_id: str, reason: Optional[str] = None):
        """Handle queue stop event."""
        self.server.broadcast_queue_status(
            queue_id=queue_id,
            status='stopped',
            message=reason or "Queue stopped by user"
        )
    
    def on_queue_log(self, queue_id: str, level: str, message: str, scan_id: Optional[str] = None):
        """Handle queue log entry."""
        self.server.broadcast_log_entry(
            queue_id=queue_id,
            level=level,
            message=message,
            scan_id=scan_id
        )


class InstrumentEventHandler:
    """
    Handles instrument status events and broadcasts to WebSocket clients.
    """
    
    def __init__(self, update_server: 'ScanUpdateServer'):
        """
        Initialize the instrument event handler.
        
        Args:
            update_server: ScanUpdateServer instance for broadcasting
        """
        self.server = update_server
    
    def on_instrument_connect(
        self,
        instrument_id: int,
        instrument_name: str,
        settings: Optional[Dict[str, Any]] = None
    ):
        """Handle instrument connection event."""
        self.server.broadcast_instrument_status(
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            status='connected',
            current_settings=settings
        )
    
    def on_instrument_disconnect(self, instrument_id: int, instrument_name: str):
        """Handle instrument disconnection event."""
        self.server.broadcast_instrument_status(
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            status='disconnected'
        )
    
    def on_instrument_error(
        self,
        instrument_id: int,
        instrument_name: str,
        error_message: str
    ):
        """Handle instrument error event."""
        self.server.broadcast_instrument_status(
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            status='error',
            error_message=error_message
        )
    
    def on_instrument_busy(
        self,
        instrument_id: int,
        instrument_name: str,
        operation: Optional[str] = None
    ):
        """Handle instrument busy event."""
        settings = {'current_operation': operation} if operation else None
        self.server.broadcast_instrument_status(
            instrument_id=instrument_id,
            instrument_name=instrument_name,
            status='busy',
            current_settings=settings
        )


def register_scan_events(update_server: 'ScanUpdateServer') -> ScanEventHandler:
    """
    Create and return a ScanEventHandler.
    
    Args:
        update_server: ScanUpdateServer instance
        
    Returns:
        Configured ScanEventHandler
    """
    return ScanEventHandler(update_server)


def register_queue_events(update_server: 'ScanUpdateServer') -> QueueEventHandler:
    """
    Create and return a QueueEventHandler.
    
    Args:
        update_server: ScanUpdateServer instance
        
    Returns:
        Configured QueueEventHandler
    """
    return QueueEventHandler(update_server)


def register_instrument_events(update_server: 'ScanUpdateServer') -> InstrumentEventHandler:
    """
    Create and return an InstrumentEventHandler.
    
    Args:
        update_server: ScanUpdateServer instance
        
    Returns:
        Configured InstrumentEventHandler
    """
    return InstrumentEventHandler(update_server)


def setup_all_handlers(update_server: 'ScanUpdateServer') -> Dict[str, Any]:
    """
    Create all event handlers at once.
    
    Args:
        update_server: ScanUpdateServer instance
        
    Returns:
        Dictionary with all handler instances
    """
    return {
        'scan': register_scan_events(update_server),
        'queue': register_queue_events(update_server),
        'instrument': register_instrument_events(update_server),
    }
