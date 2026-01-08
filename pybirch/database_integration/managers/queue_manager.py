"""
Queue Manager
=============
Manages the integration between PyBirch Queue objects and the database.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

try:
    from database.services import DatabaseService
    from database.models import Queue as DBQueue
except ImportError:
    DatabaseService = None
    DBQueue = None


class QueueManager:
    """
    Manages queue lifecycle and database synchronization.
    
    This class bridges PyBirch Queue objects with database Queue records,
    handling creation, updates, and log persistence.
    """
    
    def __init__(self, db_service: 'DatabaseService'):
        """
        Initialize the QueueManager.
        
        Args:
            db_service: Database service instance for persistence operations
        """
        self.db = db_service
        self._active_queues: Dict[str, int] = {}  # Maps queue_id to db_id
    
    def create_queue(
        self,
        name: Optional[str] = None,
        sample_id: Optional[int] = None,
        project_id: Optional[int] = None,
        queue_template_id: Optional[int] = None,
        execution_mode: str = 'SERIAL',
        operator: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a database queue record.
        
        Args:
            name: Queue name (optional)
            sample_id: Database sample ID (optional)
            project_id: Database project ID (optional)
            queue_template_id: Database queue template ID (optional)
            execution_mode: 'SERIAL' or 'PARALLEL'
            operator: Operator name
            
        Returns:
            Dictionary with created queue data
        """
        # Generate unique queue_id
        queue_id = f"Q_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        data = {
            'queue_id': queue_id,
            'name': name or f"Queue {queue_id}",
            'status': 'pending',
            'execution_mode': execution_mode,
            'sample_id': sample_id,
            'project_id': project_id,
            'queue_template_id': queue_template_id,
            'operator': operator,
            'total_scans': 0,
            'completed_scans': 0,
        }
        
        db_queue = self.db.create_queue(data)
        self._active_queues[queue_id] = db_queue['id']
        
        return db_queue
    
    def create_queue_from_pybirch(
        self,
        pybirch_queue: 'Queue',
        sample_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a database queue from a PyBirch Queue object.
        
        Args:
            pybirch_queue: PyBirch Queue object
            sample_id: Database sample ID (optional)
            project_id: Database project ID (optional)
            
        Returns:
            Dictionary with created queue data
        """
        # Generate a unique queue_id with timestamp to avoid conflicts
        # Format: QueueName_YYYYMMDD_HHMMSS_microseconds
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        unique_queue_id = f"{pybirch_queue.QID}_{timestamp}"
        
        # Queue name is the user-friendly display name (the original QID)
        queue_name = pybirch_queue.QID
        
        data = {
            'queue_id': unique_queue_id,  # Unique identifier for database
            'name': queue_name,            # User-friendly display name
            'status': pybirch_queue.state.name.lower(),
            'execution_mode': pybirch_queue.execution_mode.name,
            'sample_id': sample_id,
            'project_id': project_id,
            'total_scans': pybirch_queue.size(),
        }
        
        db_queue = self.db.create_queue(data)
        self._active_queues[unique_queue_id] = db_queue['id']
        
        return db_queue
    
    def start_queue(self, queue_id: str) -> bool:
        """
        Mark a queue as started.
        
        Args:
            queue_id: The queue ID to start
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        result = self.db.update_queue(db_id, {
            'status': 'running',
            'started_at': datetime.now()  # Use datetime object, not string
        })
        return result is not None
    
    def pause_queue(self, queue_id: str) -> bool:
        """Mark a queue as paused."""
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        result = self.db.update_queue(db_id, {'status': 'paused'})
        return result is not None
    
    def resume_queue(self, queue_id: str) -> bool:
        """Resume a paused queue."""
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        result = self.db.update_queue(db_id, {'status': 'running'})
        return result is not None
    
    def complete_queue(self, queue_id: str) -> bool:
        """Mark a queue as completed."""
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        result = self.db.update_queue(db_id, {
            'status': 'completed',
            'completed_at': datetime.now()  # Use datetime object, not string
        })
        
        if result:
            del self._active_queues[queue_id]
        
        return result is not None
    
    def stop_queue(self, queue_id: str) -> bool:
        """Mark a queue as stopped."""
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        result = self.db.update_queue(db_id, {
            'status': 'stopped',
            'completed_at': datetime.now()  # Use datetime object, not string
        })
        
        if result:
            del self._active_queues[queue_id]
        
        return result is not None
    
    def update_progress(self, queue_id: str, completed_scans: int, total_scans: Optional[int] = None) -> bool:
        """
        Update queue progress.
        
        Args:
            queue_id: The queue ID
            completed_scans: Number of completed scans
            total_scans: Total number of scans (optional, updates if provided)
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        update_data = {'completed_scans': completed_scans}
        if total_scans is not None:
            update_data['total_scans'] = total_scans
        
        result = self.db.update_queue(db_id, update_data)
        return result is not None
    
    def add_log(self, queue_id: str, level: str, message: str, scan_id: Optional[str] = None) -> bool:
        """
        Add a log entry for a queue.
        
        Args:
            queue_id: The queue ID
            level: Log level ('INFO', 'WARNING', 'ERROR')
            message: Log message
            scan_id: Associated scan ID (optional)
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        # Use the create_queue_log service method
        if hasattr(self.db, 'create_queue_log'):
            try:
                self.db.create_queue_log(db_id, level, message, scan_id)
                return True
            except Exception:
                return False
        
        return False
    
    def get_queue(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """Get queue data from database."""
        db_id = self._active_queues.get(queue_id)
        if db_id:
            return self.db.get_queue(db_id)
        return self.db.get_queue_by_queue_id(queue_id)
    
    def get_active_queues(self) -> List[Dict[str, Any]]:
        """Get all currently active queues."""
        return self.db.get_queues(status='running')[0]
    
    def sync_from_pybirch(self, pybirch_queue: 'Queue') -> bool:
        """
        Sync database queue state from PyBirch Queue object.
        
        Args:
            pybirch_queue: PyBirch Queue object
            
        Returns:
            True if successful, False otherwise
        """
        queue_id = pybirch_queue.QID
        db_id = self._get_db_id(queue_id)
        if not db_id:
            return False
        
        update_data = {
            'status': pybirch_queue.state.name.lower(),
            'execution_mode': pybirch_queue.execution_mode.name,
            'total_scans': pybirch_queue.size(),
        }
        
        result = self.db.update_queue(db_id, update_data)
        return result is not None
    
    def _get_db_id(self, queue_id: str) -> Optional[int]:
        """Get database ID for a queue."""
        if queue_id in self._active_queues:
            return self._active_queues[queue_id]
        
        # Try to find in database
        queue = self.db.get_queue_by_queue_id(queue_id) if hasattr(self.db, 'get_queue_by_queue_id') else None
        if queue:
            self._active_queues[queue_id] = queue['id']
            return queue['id']
        
        return None
