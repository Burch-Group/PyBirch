"""
PyBirch Database Extension
==========================
A ScanExtension that automatically persists scan data to the database.
"""

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Any
from threading import Lock

from pybirch.extensions.scan_extensions import ScanExtension
from pybirch.scan.movements import MovementItem

from database.session import get_db, get_session
from database.models import Scan as ScanModel, MeasurementObject, MeasurementDataPoint
from database.crud import sample_crud, scan_crud


class DatabaseExtension(ScanExtension):
    """
    Extension that persists scan data to the PyBirch database.
    
    This extension automatically:
    - Creates a database record when a scan starts
    - Saves measurement data as it's collected
    - Updates scan status throughout execution
    - Records scan completion/failure
    
    Usage:
        from database.extension import DatabaseExtension
        
        # Create extension
        db_ext = DatabaseExtension(operator="John Doe")
        
        # Add to scan settings
        scan_settings = ScanSettings(
            project_name="my_project",
            scan_name="test_scan",
            ...,
            extensions=[db_ext]
        )
    """
    
    def __init__(
        self, 
        operator: Optional[str] = None,
        auto_save_interval: int = 100,  # Save to DB every N data points
        buffer_size: int = 50
    ):
        """
        Initialize the database extension.
        
        Args:
            operator: Name of the operator running the scan
            auto_save_interval: How often to flush data to database (in data points)
            buffer_size: Number of data points to buffer before batch insert
        """
        self.operator = operator
        self.auto_save_interval = auto_save_interval
        self.buffer_size = buffer_size
        
        # Runtime state
        self._scan: Optional[Any] = None  # Reference to PyBirch Scan
        self._db_scan_id: Optional[int] = None
        self._db_sample_id: Optional[int] = None
        self._measurement_objects: Dict[str, int] = {}  # name -> db ID
        self._data_buffer: Dict[str, List[dict]] = {}
        self._sequence_indices: Dict[str, int] = {}
        self._lock = Lock()
        self._initialized = False
    
    def startup(self):
        """Called when a scan starts. Creates database records."""
        # Will be called by scan.startup(), but we need the scan reference
        # This is handled in execute() where we have access to the scan
        pass
    
    def _initialize_db_records(self, scan):
        """Initialize database records for the scan."""
        self._scan = scan
        
        with get_session() as session:
            # Get or create sample record
            if scan.sample_ID:
                sample = sample_crud.get_by_sample_id(session, scan.sample_ID)
                if not sample:
                    # Create sample from PyBirch sample if it exists
                    if hasattr(scan, 'sample') and scan.sample:
                        sample = sample_crud.from_pybirch(
                            session, 
                            scan.sample,
                            created_by=self.operator
                        )
                    else:
                        sample = sample_crud.create_sample(
                            session,
                            sample_id=scan.sample_ID,
                            created_by=self.operator
                        )
                self._db_sample_id = sample.id
            
            # Create scan record
            db_scan = scan_crud.from_pybirch(
                session,
                scan,
                sample_db_id=self._db_sample_id
            )
            db_scan.status = "running"
            db_scan.started_at = datetime.utcnow()
            db_scan.created_by = self.operator
            session.flush()
            
            self._db_scan_id = db_scan.id
            
            # Create measurement objects for each measurement item
            for item in scan.scan_settings.scan_tree.get_measurement_items():
                unique_id = item.unique_id()
                instr = item.instrument_object.instrument
                
                mobj = scan_crud.add_measurement_object(
                    session,
                    scan_id=self._db_scan_id,
                    name=unique_id,
                    instrument_name=instr.name if hasattr(instr, 'name') else instr.__class__.__name__,
                    data_type="numeric",
                    columns=instr.columns().tolist() if hasattr(instr, 'columns') else None
                )
                
                self._measurement_objects[unique_id] = mobj.id
                self._data_buffer[unique_id] = []
                self._sequence_indices[unique_id] = 0
        
        self._initialized = True
        print(f"[DatabaseExtension] Initialized scan record (ID: {self._db_scan_id})")
    
    def save_data(self, data: pd.DataFrame, measurement_name: str):
        """
        Save measurement data to the database.
        
        Called by the scan when data is collected.
        
        Args:
            data: DataFrame containing the measurement data
            measurement_name: Unique identifier for the measurement
        """
        if not self._initialized or measurement_name not in self._measurement_objects:
            return
        
        with self._lock:
            # Convert DataFrame rows to dicts
            for row in data.itertuples(index=False):
                row_dict = {col: val for col, val in zip(data.columns, row)}
                # Convert numpy types to Python types for JSON serialization
                row_dict = {k: (float(v) if hasattr(v, 'item') else v) for k, v in row_dict.items()}
                self._data_buffer[measurement_name].append(row_dict)
            
            # Flush if buffer is full
            if len(self._data_buffer[measurement_name]) >= self.buffer_size:
                self._flush_buffer(measurement_name)
    
    def _flush_buffer(self, measurement_name: str):
        """Flush buffered data to the database."""
        if not self._data_buffer[measurement_name]:
            return
        
        data_to_save = self._data_buffer[measurement_name].copy()
        self._data_buffer[measurement_name].clear()
        
        mobj_id = self._measurement_objects[measurement_name]
        start_index = self._sequence_indices[measurement_name]
        
        try:
            with get_session() as session:
                count = scan_crud.add_measurement_data_batch(
                    session,
                    measurement_object_id=mobj_id,
                    data_list=data_to_save,
                    start_index=start_index
                )
                self._sequence_indices[measurement_name] += count
        except Exception as e:
            print(f"[DatabaseExtension] Error saving data for {measurement_name}: {e}")
            # Re-add data to buffer on failure
            self._data_buffer[measurement_name] = data_to_save + self._data_buffer[measurement_name]
    
    def move_to_positions(self, items_to_move: list[tuple[MovementItem, float]]):
        """Called when instruments move to new positions."""
        # Could log position changes if needed
        pass
    
    def take_measurements(self):
        """Called when measurements are taken."""
        # Data is handled via save_data()
        pass
    
    def execute(self):
        """Called when scan execution begins."""
        if self._scan is None:
            # Try to get scan reference from the calling context
            # This is a bit hacky but necessary since extensions don't get scan reference directly
            import inspect
            frame = inspect.currentframe()
            if frame:
                outer_frames = inspect.getouterframes(frame)
                for frame_info in outer_frames:
                    if 'self' in frame_info.frame.f_locals:
                        obj = frame_info.frame.f_locals['self']
                        if hasattr(obj, 'scan_settings') and hasattr(obj, 'sample_ID'):
                            self._initialize_db_records(obj)
                            break
    
    def shutdown(self):
        """Called when scan ends. Finalizes database records."""
        if not self._initialized:
            return
        
        # Flush all remaining buffers
        for measurement_name in list(self._data_buffer.keys()):
            with self._lock:
                self._flush_buffer(measurement_name)
        
        # Update scan status
        try:
            with get_session() as session:
                scan_crud.update_status(
                    session,
                    self._db_scan_id,
                    status="completed",
                    completed_at=datetime.utcnow()
                )
            print(f"[DatabaseExtension] Scan completed and saved (ID: {self._db_scan_id})")
        except Exception as e:
            print(f"[DatabaseExtension] Error updating scan status: {e}")
        
        # Reset state
        self._initialized = False
        self._scan = None
        self._db_scan_id = None
        self._db_sample_id = None
        self._measurement_objects.clear()
        self._data_buffer.clear()
        self._sequence_indices.clear()
    
    def mark_failed(self, error: Optional[Exception] = None):
        """Mark the scan as failed in the database."""
        if not self._initialized or self._db_scan_id is None:
            return
        
        try:
            with get_session() as session:
                scan = session.get(ScanModel, self._db_scan_id)
                if scan:
                    scan.status = "failed"
                    scan.completed_at = datetime.utcnow()
                    if error:
                        scan.notes = f"Error: {str(error)}"
        except Exception as e:
            print(f"[DatabaseExtension] Error marking scan as failed: {e}")
    
    def mark_aborted(self):
        """Mark the scan as aborted in the database."""
        if not self._initialized or self._db_scan_id is None:
            return
        
        try:
            with get_session() as session:
                scan = session.get(ScanModel, self._db_scan_id)
                if scan:
                    scan.status = "aborted"
                    scan.completed_at = datetime.utcnow()
        except Exception as e:
            print(f"[DatabaseExtension] Error marking scan as aborted: {e}")


class QueueDatabaseExtension:
    """
    Extension for persisting queue information to the database.
    
    This should be used with Queue callbacks rather than as a ScanExtension.
    
    Usage:
        from database.extension import QueueDatabaseExtension
        
        queue = Queue(QID="my_queue")
        db_ext = QueueDatabaseExtension(queue, operator="John Doe")
        # Extension automatically registers callbacks
    """
    
    def __init__(self, queue, operator: Optional[str] = None):
        """
        Initialize the queue database extension.
        
        Args:
            queue: PyBirch Queue instance
            operator: Name of the operator
        """
        self.queue = queue
        self.operator = operator
        self._db_queue_id: Optional[int] = None
        self._scan_id_map: Dict[str, int] = {}  # pybirch scan_id -> db scan id
        
        # Register callbacks
        queue.add_state_callback(self._on_state_change)
        queue.add_log_callback(self._on_log)
        
        # Create initial queue record
        self._create_queue_record()
    
    def _create_queue_record(self):
        """Create the queue record in the database."""
        from database.crud import queue_crud
        
        try:
            with get_session() as session:
                db_queue = queue_crud.from_pybirch(session, self.queue)
                db_queue.created_by = self.operator
                session.flush()
                self._db_queue_id = db_queue.id
            print(f"[QueueDatabaseExtension] Created queue record (ID: {self._db_queue_id})")
        except Exception as e:
            print(f"[QueueDatabaseExtension] Error creating queue record: {e}")
    
    def _on_state_change(self, scan_id: str, state):
        """Handle scan state changes."""
        from database.crud import queue_crud
        from pybirch.queue.queue import ScanState
        
        if self._db_queue_id is None:
            return
        
        try:
            with get_session() as session:
                # Map state to string
                status_map = {
                    ScanState.QUEUED: "pending",
                    ScanState.RUNNING: "running",
                    ScanState.PAUSED: "paused",
                    ScanState.COMPLETED: "completed",
                    ScanState.ABORTED: "aborted",
                    ScanState.FAILED: "failed"
                }
                
                # Update queue status and scan count
                queue = session.get(queue_crud.model, self._db_queue_id)
                if queue:
                    # Count completed scans
                    completed = sum(
                        1 for h in self.queue._scan_handles 
                        if h.state in (ScanState.COMPLETED, ScanState.FAILED, ScanState.ABORTED)
                    )
                    queue.completed_scans = completed
                    
                    # Update queue status based on overall state
                    if self.queue.state.name == "RUNNING":
                        queue.status = "running"
                    elif self.queue.state.name == "PAUSED":
                        queue.status = "paused"
                    elif self.queue.state.name == "IDLE":
                        if completed == queue.total_scans:
                            queue.status = "completed"
                            queue.completed_at = datetime.utcnow()
                    
        except Exception as e:
            print(f"[QueueDatabaseExtension] Error updating state: {e}")
    
    def _on_log(self, log_entry):
        """Handle log entries (optional: could save to audit log)."""
        pass
    
    def cleanup(self):
        """Remove callbacks and cleanup."""
        try:
            self.queue.remove_state_callback(self._on_state_change)
            self.queue.remove_log_callback(self._on_log)
        except:
            pass
