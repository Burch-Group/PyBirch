"""
Database Extension
==================
PyBirch scan extension that syncs scan data to the database in real-time.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd

try:
    from pybirch.extensions.scan_extensions import ScanExtension
except ImportError:
    # Fallback if ScanExtension not available
    class ScanExtension:
        def __init__(self): pass
        def startup(self): pass
        def save_data(self, data, measurement_name): pass
        def execute(self): pass
        def shutdown(self): pass

try:
    from database.services import DatabaseService
except ImportError:
    DatabaseService = None

from ..managers.scan_manager import ScanManager
from ..managers.data_manager import DataManager
from ..managers.queue_manager import QueueManager


class DatabaseExtension(ScanExtension):
    """
    PyBirch scan extension that automatically syncs scan data to the database.
    
    This extension integrates with PyBirch's extension system to:
    - Track scan lifecycle (start, pause, resume, complete, abort)
    - Persist measurement data to the database
    - Update scan status in real-time
    
    Usage:
        from pybirch.database_integration import DatabaseExtension
        from database.services import DatabaseService
        
        db = DatabaseService('path/to/db.db')
        extension = DatabaseExtension(db, sample_id=1, project_id=1)
        
        # Add to scan settings
        scan_settings = ScanSettings(
            project_name="my_project",
            scan_name="test_scan",
            scan_type="1D Scan",
            job_type="Raman",
            ScanTree=scan_tree,
            extensions=[extension]  # Include the database extension
        )
        
        scan = Scan(scan_settings, owner="user", sample_ID="S001")
        scan.run_scan()  # Extension hooks are called automatically
    """
    
    def __init__(
        self,
        db_service: 'DatabaseService',
        sample_id: Optional[int] = None,
        project_id: Optional[int] = None,
        queue_id: Optional[int] = None,
        buffer_size: int = 100,
        owner: Optional[str] = None,
        scan_settings: Optional['ScanSettings'] = None,
    ):
        """
        Initialize the DatabaseExtension.
        
        Args:
            db_service: Database service instance
            sample_id: Database sample ID to associate with scan
            project_id: Database project ID to associate with scan
            queue_id: Database queue ID if part of a queue
            buffer_size: Number of data points to buffer before flushing
            owner: Owner/operator name (will use scan.owner if not provided)
            scan_settings: Optional ScanSettings to capture at init time
        """
        # Note: We don't call super().__init__() because ScanExtension raises NotImplementedError
        self.db = db_service
        self.sample_id = sample_id
        self.project_id = project_id
        self.queue_id = queue_id
        self.buffer_size = buffer_size
        self.owner = owner
        self._scan_settings = scan_settings
        
        # Initialize managers
        self.scan_manager = ScanManager(db_service)
        self.data_manager = DataManager(db_service, buffer_size=buffer_size)
        self.queue_manager = QueueManager(db_service) if queue_id else None
        
        # State tracking
        self._db_scan: Optional[Dict] = None
        self._scan_id: Optional[str] = None
        self._started: bool = False
        self._completed: bool = False
        self._scan_ref: Optional['Scan'] = None  # Reference to parent scan
    
    @property
    def db_scan_id(self) -> Optional[int]:
        """Get the database scan ID."""
        return self._db_scan['id'] if self._db_scan else None
    
    @property
    def scan_id(self) -> Optional[str]:
        """Get the scan ID string."""
        return self._scan_id
    
    def set_scan_reference(self, scan: 'Scan'):
        """
        Set a reference to the parent Scan object.
        Call this before startup() if you need access to scan properties.
        
        Args:
            scan: The PyBirch Scan object
        """
        self._scan_ref = scan
        self._scan_settings = scan.scan_settings
        if not self.owner:
            self.owner = scan.owner
    
    def startup(self):
        """
        Called when the scan is starting up (by Scan.startup()).
        Creates the database record for this scan.
        """
        print(f"[DB] DatabaseExtension.startup() called")
        print(f"[DB]   scan_settings: {self._scan_settings}")
        print(f"[DB]   sample_id: {self.sample_id}, project_id: {self.project_id}, queue_id: {self.queue_id}")
        
        # If we have a scan reference, use it; otherwise use stored settings
        scan_settings = self._scan_settings
        
        if scan_settings is None:
            print("[DB] Warning: DatabaseExtension.startup() called without scan_settings")
            return
        
        # Create database scan record
        self._db_scan = self.scan_manager.create_scan(
            scan_settings,
            sample_id=self.sample_id,
            project_id=self.project_id,
            queue_id=self.queue_id,
            owner=self.owner,
        )
        
        self._scan_id = self._db_scan['scan_id']
        print(f"[DB] Scan created: {self._scan_id} (ID: {self.db_scan_id})")
    
    def execute(self):
        """
        Called when scan execution begins (by Scan.execute()).
        Marks the scan as running in the database.
        """
        if not self._db_scan:
            return
        
        self.scan_manager.start_scan(self._scan_id)
        self._started = True
        print(f"[DB] Scan started: {self._scan_id}")
        
        # Add log entry to queue if part of a queue
        if self.queue_id:
            try:
                self.db.create_queue_log(
                    self.queue_id, 'INFO',
                    f"Scan started: {self._scan_id}",
                    scan_id=self._scan_id
                )
            except Exception as e:
                print(f"[DB] Failed to add queue log: {e}")
    
    def save_data(self, data: pd.DataFrame, measurement_name: str):
        """
        Called by Scan._save_data_async() for each measurement batch.
        Persists measurement data to the database.
        
        Args:
            data: DataFrame containing measurement data
            measurement_name: Name/ID of the measurement (e.g., instrument unique_id)
        """
        print(f"[DB] save_data called: measurement={measurement_name}, rows={len(data)}, db_scan={self._db_scan}, completed={self._completed}")
        
        if not self._db_scan:
            print(f"[DB] ERROR: No db_scan record - skipping save_data for {measurement_name}")
            return
        if self._completed:
            print(f"[DB] WARNING: Scan already completed - skipping save_data for {measurement_name}")
            return
        
        # Extract instrument name from measurement_name if possible
        # Format is typically "InstrumentName_index" or similar
        instrument_name = measurement_name.split('_')[0] if '_' in measurement_name else measurement_name
        
        # Save to database through data manager
        count = self.data_manager.save_dataframe(
            self.db_scan_id,
            measurement_name,
            data,
            instrument_name=instrument_name
        )
        
        # Debug logging
        print(f"[DB] Saved {count} data points for {measurement_name}")
    
    def save_array(
        self,
        data,  # np.ndarray
        measurement_name: str,
        extra_data: Optional[Dict] = None,
    ):
        """
        Save array data (spectra, images, etc.).
        
        Args:
            data: NumPy array to save
            measurement_name: Name/ID of the measurement
            extra_data: Additional metadata
        """
        if not self._db_scan or self._completed:
            return
        
        self.data_manager.save_array(
            self.db_scan_id,
            measurement_name,
            data,
            extra_data=extra_data
        )
    
    def on_pause(self):
        """Called when scan is paused."""
        if not self._db_scan:
            return
        
        self.data_manager.flush(self.db_scan_id)
        self.scan_manager.pause_scan(self._scan_id)
        print(f"Database scan paused: {self._scan_id}")
    
    def on_resume(self):
        """Called when scan is resumed."""
        if not self._db_scan:
            return
        
        self.scan_manager.resume_scan(self._scan_id)
        print(f"Database scan resumed: {self._scan_id}")
    
    def on_complete(self, wandb_link: Optional[str] = None):
        """
        Called when scan completes successfully.
        
        Args:
            wandb_link: Optional W&B run link
        """
        if not self._db_scan or self._completed:
            return
        
        # Flush any remaining data
        self.data_manager.flush(self.db_scan_id)
        
        # Update scan duration
        self.scan_manager.update_scan_duration(self._scan_id)
        
        # Mark as completed
        self.scan_manager.complete_scan(self._scan_id, wandb_link=wandb_link)
        self._completed = True
        
        data_count = self.data_manager.get_data_count(self.db_scan_id)
        print(f"[DB] Scan completed: {self._scan_id} ({data_count} data points)")
        
        # Update queue progress if part of a queue
        if self.queue_id:
            try:
                # Get current queue state to calculate completed scans
                queue = self.db.get_queue(self.queue_id)
                if queue:
                    completed = (queue.get('completed_scans') or 0) + 1
                    total = queue.get('total_scans') or 0
                    
                    # Build update dict
                    update_data = {'completed_scans': completed}
                    
                    # Check if all scans are done - mark queue as completed
                    if completed >= total and total > 0:
                        from datetime import datetime
                        update_data['status'] = 'completed'
                        update_data['completed_at'] = datetime.now()
                        print(f"[DB] Queue completed: all {total} scans finished")
                    
                    # Update queue
                    self.db.update_queue(self.queue_id, update_data)
                    
                    # Add log entry
                    log_message = f"Scan completed: {self._scan_id} ({completed}/{total})"
                    if completed >= total and total > 0:
                        log_message = f"Queue completed: {self._scan_id} was final scan ({completed}/{total})"
                    
                    self.db.create_queue_log(
                        self.queue_id, 'INFO',
                        log_message,
                        scan_id=self._scan_id
                    )
                    print(f"[DB] Updated queue progress: {completed}/{total}")
            except Exception as e:
                print(f"[DB] Failed to update queue progress: {e}")
                import traceback
                traceback.print_exc()
    
    def on_abort(self):
        """Called when scan is aborted."""
        if not self._db_scan or self._completed:
            return
        
        # Flush any data collected so far
        self.data_manager.flush(self.db_scan_id)
        
        # Mark as aborted
        self.scan_manager.abort_scan(self._scan_id)
        self._completed = True
        print(f"Database scan aborted: {self._scan_id}")
    
    def on_error(self, error: Exception):
        """
        Called when scan encounters an error.
        
        Args:
            error: The exception that occurred
        """
        if not self._db_scan or self._completed:
            return
        
        # Flush any data collected so far
        self.data_manager.flush(self.db_scan_id)
        
        # Mark as failed
        self.scan_manager.fail_scan(self._scan_id, error_message=str(error))
        self._completed = True
        print(f"[DB] Scan failed: {self._scan_id} - {error}")
    
    def shutdown(self):
        """
        Called when the scan is shutdown (by Scan.shutdown()).
        Completes the database record if not already completed.
        """
        if not self._db_scan:
            return
        
        if not self._completed:
            # Get wandb link if available from scan reference
            wandb_link = None
            if self._scan_ref and hasattr(self._scan_ref, 'run') and self._scan_ref.run:
                try:
                    wandb_link = self._scan_ref.run.get_url()
                except Exception:
                    pass
            
            self.on_complete(wandb_link=wandb_link)
    
    def flush(self):
        """Flush all buffered data to database."""
        if self._db_scan:
            self.data_manager.flush(self.db_scan_id)
    
    def get_data(self, measurement_name: str) -> pd.DataFrame:
        """
        Get measurement data from database.
        
        Args:
            measurement_name: Name of the measurement
            
        Returns:
            DataFrame with measurement data
        """
        if not self._db_scan:
            return pd.DataFrame()
        
        return self.data_manager.get_data(self.db_scan_id, measurement_name)
    
    def get_scan_info(self) -> Optional[Dict[str, Any]]:
        """Get current scan information from database."""
        if not self._scan_id:
            return None
        return self.scan_manager.get_scan(self._scan_id)
    
    def __del__(self):
        """Cleanup on destruction."""
        # Ensure data is flushed
        if self._db_scan and not self._completed:
            try:
                self.flush()
            except Exception:
                pass


class DatabaseQueueExtension:
    """
    Extension for tracking queue execution in the database.
    
    Usage:
        from pybirch.database_integration import DatabaseQueueExtension
        from database.services import get_db_service
        
        db = get_db_service()
        queue_ext = DatabaseQueueExtension(db, project_id=1)
        
        # When creating queue
        queue_ext.on_queue_create(queue)
        
        # When queue starts
        queue_ext.on_queue_start()
        
        # For each scan
        scan_ext = queue_ext.create_scan_extension(sample_id=1)
        scan = Scan(settings, sample, extensions=[scan_ext])
    """
    
    def __init__(
        self,
        db_service: 'DatabaseService',
        project_id: Optional[int] = None,
        operator: Optional[str] = None,
    ):
        """
        Initialize the DatabaseQueueExtension.
        
        Args:
            db_service: Database service instance
            project_id: Database project ID
            operator: Operator name
        """
        from ..managers.queue_manager import QueueManager
        
        self.db = db_service
        self.project_id = project_id
        self.operator = operator
        
        self.queue_manager = QueueManager(db_service)
        
        self._db_queue: Optional[Dict] = None
        self._queue_id: Optional[str] = None
        self._scan_count: int = 0
    
    @property
    def db_queue_id(self) -> Optional[int]:
        """Get the database queue ID."""
        return self._db_queue['id'] if self._db_queue else None
    
    def on_queue_create(self, pybirch_queue: 'Queue', sample_id: Optional[int] = None):
        """
        Called when queue is created.
        
        Args:
            pybirch_queue: PyBirch Queue object
            sample_id: Database sample ID
        """
        self._db_queue = self.queue_manager.create_queue_from_pybirch(
            pybirch_queue,
            sample_id=sample_id,
            project_id=self.project_id,
        )
        self._queue_id = self._db_queue['queue_id']
        print(f"Database queue created: {self._queue_id}")
    
    def on_queue_start(self):
        """Called when queue starts executing."""
        if self._queue_id:
            self.queue_manager.start_queue(self._queue_id)
            print(f"Database queue started: {self._queue_id}")
    
    def on_queue_pause(self):
        """Called when queue is paused."""
        if self._queue_id:
            self.queue_manager.pause_queue(self._queue_id)
    
    def on_queue_resume(self):
        """Called when queue is resumed."""
        if self._queue_id:
            self.queue_manager.resume_queue(self._queue_id)
    
    def on_queue_complete(self):
        """Called when queue completes."""
        if self._queue_id:
            self.queue_manager.complete_queue(self._queue_id)
            print(f"Database queue completed: {self._queue_id}")
    
    def on_queue_stop(self):
        """Called when queue is stopped."""
        if self._queue_id:
            self.queue_manager.stop_queue(self._queue_id)
    
    def on_scan_complete(self):
        """Called when a scan in the queue completes."""
        self._scan_count += 1
        if self._queue_id:
            self.queue_manager.update_progress(self._queue_id, self._scan_count)
    
    def log(self, level: str, message: str, scan_id: Optional[str] = None):
        """
        Add a log entry.
        
        Args:
            level: Log level ('INFO', 'WARNING', 'ERROR')
            message: Log message
            scan_id: Associated scan ID
        """
        if self._queue_id:
            self.queue_manager.add_log(self._queue_id, level, message, scan_id)
    
    def create_scan_extension(
        self,
        sample_id: Optional[int] = None,
        buffer_size: int = 100,
    ) -> DatabaseExtension:
        """
        Create a DatabaseExtension for a scan in this queue.
        
        Args:
            sample_id: Database sample ID
            buffer_size: Data buffer size
            
        Returns:
            DatabaseExtension configured for this queue
        """
        return DatabaseExtension(
            self.db,
            sample_id=sample_id,
            project_id=self.project_id,
            queue_id=self.db_queue_id,
            buffer_size=buffer_size,
            owner=self.operator,
        )
