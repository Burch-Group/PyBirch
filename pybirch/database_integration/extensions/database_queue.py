"""
Database Queue
==============
PyBirch Queue extension that automatically tracks queue execution in the database.

This module provides `DatabaseQueue`, a subclass of PyBirch's Queue that:
- Automatically creates database records for queues and their scans
- Tracks scan state changes in real-time
- Persists queue logs to the database
- Supports queue recovery from database state after crashes
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from threading import Lock
import traceback

# Import PyBirch Queue classes
try:
    from pybirch.queue.queue import (
        Queue, ScanHandle, ScanState, QueueState, ExecutionMode, LogEntry
    )
except ImportError:
    # Fallback - queue not available
    raise ImportError("PyBirch queue module is required for DatabaseQueue")

# Import database components
try:
    from database.services import DatabaseService
except ImportError:
    DatabaseService = None

from ..managers.queue_manager import QueueManager
from ..managers.scan_manager import ScanManager
from ..managers.data_manager import DataManager
from .database_extension import DatabaseExtension


class DatabaseQueue(Queue):
    """
    A Queue subclass that automatically syncs state to the database.
    
    This class extends PyBirch's Queue to automatically:
    - Create database records when the queue is created
    - Track individual scan lifecycle states
    - Persist log entries to the database
    - Update progress as scans complete
    - Support recovery from database state
    
    Usage:
        from pybirch.database_integration import DatabaseQueue
        from database.services import DatabaseService
        
        db = DatabaseService('path/to/db.db')
        
        # Create a new queue with database tracking
        queue = DatabaseQueue(
            QID="my_queue",
            db_service=db,
            project_id=1,
            sample_id=1
        )
        
        # Add scans - they automatically get database extensions
        queue.enqueue(scan)
        
        # Start execution - database is updated in real-time
        queue.start()
        
        # Recovery: reconstruct queue from database
        recovered_queue = DatabaseQueue.from_database(db, "Q_20240101_120000_abc123")
    
    Attributes:
        db_service: Database service instance
        queue_manager: QueueManager for queue operations
        scan_manager: ScanManager for scan operations
        data_manager: DataManager for measurement data
        db_queue_id: Database ID of the queue record
        project_id: Associated project ID
        sample_id: Associated sample ID
    """
    
    def __init__(
        self,
        QID: str,
        db_service: 'DatabaseService',
        project_id: Optional[int] = None,
        sample_id: Optional[int] = None,
        operator: Optional[str] = None,
        scans: Optional[List['Scan']] = None,
        max_parallel_scans: int = 4,
        auto_create_db_record: bool = True,
        buffer_size: int = 100,
        update_server: Optional[Any] = None,
    ):
        """
        Initialize DatabaseQueue.
        
        Args:
            QID: Queue ID string
            db_service: Database service instance
            project_id: Database project ID to associate with queue/scans
            sample_id: Database sample ID to associate with scans
            operator: Operator name for logging
            scans: Initial list of scans to enqueue
            max_parallel_scans: Maximum parallel scan execution
            auto_create_db_record: If True, create DB record immediately
            buffer_size: Data buffer size for scan extensions
            update_server: Optional ScanUpdateServer for WebSocket broadcasts
        """
        # Initialize parent Queue
        super().__init__(QID=QID, scans=None, max_parallel_scans=max_parallel_scans)
        
        # Database components
        self.db_service = db_service
        self.queue_manager = QueueManager(db_service)
        self.scan_manager = ScanManager(db_service)
        self.data_manager = DataManager(db_service, buffer_size=buffer_size)
        
        # Configuration
        self.project_id = project_id
        self.sample_id = sample_id
        self.operator = operator
        self.buffer_size = buffer_size
        
        # WebSocket integration
        self.update_server = update_server
        self._websocket_bridge = None
        
        # Database state
        self._db_queue: Optional[Dict] = None
        self._db_lock = Lock()
        self._scan_extensions: Dict[str, DatabaseExtension] = {}  # scan_id -> extension
        
        # Setup callbacks to track state changes
        self._setup_db_callbacks()
        
        # Setup WebSocket integration if server provided
        if update_server:
            self._setup_websocket_integration()
        
        # Create database record if requested
        if auto_create_db_record:
            self._create_db_record()
        
        # Add initial scans if provided
        if scans:
            for scan in scans:
                self.enqueue(scan)
    
    @property
    def db_queue_id(self) -> Optional[int]:
        """Get the database queue ID."""
        return self._db_queue['id'] if self._db_queue else None
    
    @property
    def db_queue_uuid(self) -> Optional[str]:
        """Get the database queue UUID string."""
        return self._db_queue.get('queue_id') if self._db_queue else None
    
    def _create_db_record(self):
        """Create the database queue record."""
        with self._db_lock:
            self._db_queue = self.queue_manager.create_queue(
                name=f"Queue {self.QID}",
                sample_id=self.sample_id,
                project_id=self.project_id,
                execution_mode=self._execution_mode.name,
                operator=self.operator,
            )
            print(f"[DB Queue] Created: {self.db_queue_uuid} (ID: {self.db_queue_id})")
    
    def _setup_db_callbacks(self):
        """Setup callbacks to sync state changes to database."""
        # Add log callback to persist logs
        self.add_log_callback(self._on_log_entry)
        
        # Add state callback to track scan state changes
        self.add_state_callback(self._on_scan_state_change)
        
        # Add progress callback (optional, for fine-grained tracking)
        self.add_progress_callback(self._on_scan_progress)
    
    def _setup_websocket_integration(self):
        """Setup WebSocket integration for real-time broadcasts."""
        if not self.update_server:
            return
        
        try:
            from ..sync.websocket_integration import WebSocketQueueBridge
            self._websocket_bridge = WebSocketQueueBridge(
                queue=self,
                update_server=self.update_server,
                queue_id=self.db_queue_uuid or self.QID
            )
            print(f"[DB Queue] WebSocket integration enabled for {self.QID}")
        except ImportError as e:
            print(f"[DB Queue] Warning: Could not setup WebSocket integration: {e}")
        except Exception as e:
            print(f"[DB Queue] Warning: WebSocket integration failed: {e}")
    
    def enable_websocket_integration(self, update_server):
        """
        Enable WebSocket integration after queue creation.
        
        Args:
            update_server: ScanUpdateServer for WebSocket broadcasts
        """
        self.update_server = update_server
        self._setup_websocket_integration()
    
    def disable_websocket_integration(self):
        """Disable WebSocket integration and unregister callbacks."""
        if self._websocket_bridge:
            self._websocket_bridge.unregister()
            self._websocket_bridge = None
            self.update_server = None
            print(f"[DB Queue] WebSocket integration disabled for {self.QID}")
    
    def _on_log_entry(self, entry: LogEntry):
        """Callback for log entries - persists to database."""
        if not self._db_queue:
            return
        
        try:
            self.queue_manager.add_log(
                queue_id=self.db_queue_uuid,
                level=entry.level,
                message=entry.message,
                scan_id=entry.scan_id
            )
        except Exception as e:
            # Don't let database errors affect queue operation
            print(f"[DB Queue] Warning: Failed to persist log: {e}")
    
    def _on_scan_state_change(self, scan_id: str, state: ScanState):
        """Callback for scan state changes - updates database."""
        if not self._db_queue:
            return
        
        try:
            # Get the extension for this scan
            ext = self._scan_extensions.get(scan_id)
            if not ext:
                return
            
            # Map scan state to extension calls
            if state == ScanState.RUNNING:
                ext.execute()
            elif state == ScanState.PAUSED:
                ext.on_pause()
            elif state == ScanState.COMPLETED:
                ext.on_complete()
                self._update_queue_progress()
            elif state == ScanState.ABORTED:
                ext.on_abort()
                self._update_queue_progress()
            elif state == ScanState.FAILED:
                handle = self.get_handle_by_id(scan_id)
                if handle and handle.error:
                    ext.on_error(handle.error)
                else:
                    ext.on_error(Exception("Scan failed"))
                self._update_queue_progress()
        except Exception as e:
            print(f"[DB Queue] Warning: Failed to update scan state: {e}")
    
    def _on_scan_progress(self, scan_id: str, progress: float):
        """Callback for scan progress updates."""
        # Could be used for fine-grained progress tracking if needed
        pass
    
    def _update_queue_progress(self):
        """Update queue progress in database."""
        if not self._db_queue:
            return
        
        try:
            completed = len(self.get_handles_by_state(ScanState.COMPLETED))
            failed = len(self.get_handles_by_state(ScanState.FAILED))
            aborted = len(self.get_handles_by_state(ScanState.ABORTED))
            
            total_finished = completed + failed + aborted
            
            self.queue_manager.update_progress(
                self.db_queue_uuid,
                completed_scans=total_finished,
                total_scans=self.size()
            )
        except Exception as e:
            print(f"[DB Queue] Warning: Failed to update progress: {e}")
    
    def enqueue(self, scan: 'Scan', auto_add_extension: bool = True) -> ScanHandle:
        """
        Add a scan to the queue with automatic database tracking.
        
        Args:
            scan: The Scan object to enqueue
            auto_add_extension: If True, automatically add DatabaseExtension
            
        Returns:
            ScanHandle for the enqueued scan
        """
        handle = super().enqueue(scan)
        
        if auto_add_extension and self.db_service:
            # Create and attach database extension
            ext = DatabaseExtension(
                db_service=self.db_service,
                sample_id=self.sample_id,
                project_id=self.project_id,
                queue_id=self.db_queue_id,
                buffer_size=self.buffer_size,
                owner=self.operator or scan.owner,
                scan_settings=scan.scan_settings,
            )
            
            # Add extension to scan
            if not hasattr(scan.scan_settings, 'extensions') or scan.scan_settings.extensions is None:
                scan.scan_settings.extensions = []
            scan.scan_settings.extensions.append(ext)
            
            # Track the extension
            self._scan_extensions[handle.scan_id] = ext
            
            # Update total scans in database
            if self._db_queue:
                self.queue_manager.update_progress(
                    self.db_queue_uuid,
                    completed_scans=0,
                    total_scans=self.size()
                )
        
        return handle
    
    def start(self, indices: Optional[List[int]] = None, mode: Optional[ExecutionMode] = None):
        """
        Start queue execution with database tracking.
        
        Args:
            indices: List of scan indices to execute
            mode: Execution mode (SERIAL or PARALLEL)
        """
        # Update database queue status
        if self._db_queue:
            self.queue_manager.start_queue(self.db_queue_uuid)
        
        # Call parent start
        super().start(indices=indices, mode=mode)
    
    def pause(self, scan_id: Optional[str] = None):
        """Pause with database update."""
        super().pause(scan_id)
        
        if not scan_id and self._db_queue:
            self.queue_manager.pause_queue(self.db_queue_uuid)
    
    def resume(self, scan_id: Optional[str] = None):
        """Resume with database update."""
        super().resume(scan_id)
        
        if not scan_id and self._db_queue:
            self.queue_manager.resume_queue(self.db_queue_uuid)
    
    def abort(self, scan_id: Optional[str] = None):
        """Abort with database update."""
        super().abort(scan_id)
        
        if not scan_id and self._db_queue:
            self.queue_manager.stop_queue(self.db_queue_uuid)
    
    def stop_queue(self):
        """Stop queue with database update."""
        super().stop_queue()
        
        if self._db_queue:
            self.queue_manager.stop_queue(self.db_queue_uuid)
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all scans to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if completed, False if timed out
        """
        result = super().wait_for_completion(timeout)
        
        # Update final queue status
        if result and self._db_queue:
            all_completed = all(
                h.is_finished() for h in self._scan_handles
            )
            
            if all_completed:
                self.queue_manager.complete_queue(self.db_queue_uuid)
                print(f"[DB Queue] Completed: {self.db_queue_uuid}")
        
        return result
    
    def get_scan_extension(self, scan_id: str) -> Optional[DatabaseExtension]:
        """
        Get the DatabaseExtension for a specific scan.
        
        Args:
            scan_id: The scan ID string
            
        Returns:
            DatabaseExtension or None
        """
        return self._scan_extensions.get(scan_id)
    
    def get_db_scan_id(self, scan_id: str) -> Optional[int]:
        """
        Get the database scan ID for a PyBirch scan ID.
        
        Args:
            scan_id: The PyBirch scan ID string
            
        Returns:
            Database scan ID or None
        """
        ext = self._scan_extensions.get(scan_id)
        return ext.db_scan_id if ext else None
    
    def get_queue_data(self) -> Optional[Dict[str, Any]]:
        """Get full queue data from database."""
        if not self._db_queue:
            return None
        return self.queue_manager.get_queue(self.db_queue_uuid)
    
    def get_queue_logs(self, level: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Get queue logs from database.
        
        Args:
            level: Filter by log level
            limit: Maximum number of logs
            
        Returns:
            List of log entries
        """
        if not self._db_queue:
            return []
        
        # This would need a corresponding service method
        # For now, return in-memory logs
        logs = self.get_logs(level=level, limit=limit)
        return [
            {
                'timestamp': l.timestamp.isoformat(),
                'scan_id': l.scan_id,
                'level': l.level,
                'message': l.message,
            }
            for l in logs
        ]
    
    # ==================== Recovery Methods ====================
    
    @classmethod
    def from_database(
        cls,
        db_service: 'DatabaseService',
        queue_uuid: str,
        max_parallel_scans: int = 4,
    ) -> Optional['DatabaseQueue']:
        """
        Recover/reconstruct a queue from database state.
        
        This is useful for recovering after a crash or restart.
        Note: This reconstructs the queue record but scans need to
        be re-created with their instruments.
        
        Args:
            db_service: Database service instance
            queue_uuid: The queue UUID to recover
            max_parallel_scans: Max parallel scans
            
        Returns:
            DatabaseQueue instance or None if not found
        """
        queue_manager = QueueManager(db_service)
        
        # Get queue data from database
        db_queue = queue_manager.get_queue(queue_uuid)
        if not db_queue:
            print(f"[DB Queue] Queue not found: {queue_uuid}")
            return None
        
        # Create queue instance without auto-creating DB record
        queue = cls(
            QID=db_queue.get('queue_id', queue_uuid),
            db_service=db_service,
            project_id=db_queue.get('project_id'),
            sample_id=db_queue.get('sample_id'),
            operator=db_queue.get('operator'),
            max_parallel_scans=max_parallel_scans,
            auto_create_db_record=False,  # Don't create new record
        )
        
        # Attach existing database record
        queue._db_queue = db_queue
        
        # Set execution mode from database
        exec_mode = db_queue.get('execution_mode', 'SERIAL')
        queue._execution_mode = ExecutionMode[exec_mode]
        
        # Note: Actual scans need to be re-created by the caller
        # with their instrument instances, then added via enqueue()
        
        print(f"[DB Queue] Recovered: {queue_uuid} (status: {db_queue.get('status')})")
        return queue
    
    def get_incomplete_scans(self) -> List[Dict[str, Any]]:
        """
        Get scans that were not completed (for recovery).
        
        Returns:
            List of scan data dictionaries for incomplete scans
        """
        if not self._db_queue:
            return []
        
        # Get all scans for this queue
        scans = self.scan_manager.get_scans_for_queue(self.db_queue_id)
        
        # Filter to incomplete ones
        incomplete = [
            s for s in scans
            if s.get('status') not in ('completed', 'aborted', 'failed')
        ]
        
        return incomplete
    
    def mark_incomplete_scans_failed(self, error_message: str = "Queue interrupted"):
        """
        Mark any incomplete scans as failed (for cleanup after crash).
        
        Args:
            error_message: Error message to record
        """
        incomplete = self.get_incomplete_scans()
        
        for scan_data in incomplete:
            scan_id = scan_data.get('scan_id')
            if scan_id:
                self.scan_manager.fail_scan(scan_id, error_message=error_message)
                print(f"[DB Queue] Marked as failed: {scan_id}")
    
    def serialize(self) -> dict:
        """Serialize the queue including database info."""
        data = super().serialize()
        
        # Add database info
        data['db_queue_id'] = self.db_queue_id
        data['db_queue_uuid'] = self.db_queue_uuid
        data['project_id'] = self.project_id
        data['sample_id'] = self.sample_id
        data['operator'] = self.operator
        
        return data
    
    def __repr__(self) -> str:
        db_info = f", db_id={self.db_queue_id}" if self.db_queue_id else ""
        return f"DatabaseQueue(QID='{self.QID}', scans={self.size()}, state={self._state.name}{db_info})"
