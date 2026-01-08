"""
Scan Manager
============
Manages the integration between PyBirch Scan objects and the database.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import json

# Import will work when database module is available
try:
    from database.services import DatabaseService
    from database.models import Scan as DBScan, ScanTemplate
except ImportError:
    DatabaseService = None
    DBScan = None
    ScanTemplate = None


class ScanManager:
    """
    Manages scan lifecycle and database synchronization.
    
    This class bridges PyBirch Scan objects with database Scan records,
    handling creation, updates, and data persistence.
    """
    
    def __init__(self, db_service: 'DatabaseService'):
        """
        Initialize the ScanManager.
        
        Args:
            db_service: Database service instance for persistence operations
        """
        self.db = db_service
        self._active_scans: Dict[str, int] = {}  # Maps scan_id to db_id
    
    def create_scan(
        self,
        scan_settings: 'ScanSettings',
        sample_id: Optional[int] = None,
        queue_id: Optional[int] = None,
        project_id: Optional[int] = None,
        scan_template_id: Optional[int] = None,
        owner: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a database scan record from PyBirch ScanSettings.
        
        Args:
            scan_settings: PyBirch ScanSettings object
            sample_id: Database sample ID (optional)
            queue_id: Database queue ID (optional)
            project_id: Database project ID (optional)
            scan_template_id: Database scan template ID (optional)
            owner: Owner/operator name
            
        Returns:
            Dictionary with created scan data
        """
        # Generate unique scan_id with milliseconds for uniqueness
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S') + f'_{now.microsecond // 1000:03d}'
        scan_id = f"{scan_settings.project_name}_{scan_settings.scan_name}_{timestamp}"
        
        # Serialize scan tree if available
        scan_tree_data = None
        if hasattr(scan_settings, 'scan_tree') and scan_settings.scan_tree:
            try:
                scan_tree_data = scan_settings.scan_tree.serialize()
            except Exception:
                pass
        
        data = {
            'scan_id': scan_id,
            'project_name': scan_settings.project_name,
            'scan_name': scan_settings.scan_name,
            'scan_type': scan_settings.scan_type,
            'job_type': scan_settings.job_type,
            'status': 'pending',
            'created_by': owner,  # Database uses 'created_by' instead of 'owner'
            'scan_tree_data': scan_tree_data,
            'additional_tags': getattr(scan_settings, 'additional_tags', []),
            'sample_id': sample_id,
            'queue_id': queue_id,
            'project_id': project_id,
            'scan_template_id': scan_template_id,
        }
        
        # Handle user_fields as extra_data
        if hasattr(scan_settings, 'user_fields') and scan_settings.user_fields:
            data['extra_data'] = {'user_fields': scan_settings.user_fields}
        
        db_scan = self.db.create_scan(data)
        self._active_scans[scan_id] = db_scan['id']
        
        return db_scan
    
    def start_scan(self, scan_id: str) -> bool:
        """
        Mark a scan as started.
        
        Args:
            scan_id: The scan ID to start
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._active_scans.get(scan_id)
        if not db_id:
            # Try to find by scan_id in database
            scan = self.db.get_scan_by_scan_id(scan_id)
            if scan:
                db_id = scan['id']
                self._active_scans[scan_id] = db_id
            else:
                return False
        
        result = self.db.update_scan(db_id, {
            'status': 'running',
            'started_at': datetime.now()  # Use datetime object, not string
        })
        return result is not None
    
    def pause_scan(self, scan_id: str) -> bool:
        """Mark a scan as paused."""
        db_id = self._active_scans.get(scan_id)
        if not db_id:
            return False
        
        result = self.db.update_scan(db_id, {'status': 'paused'})
        return result is not None
    
    def resume_scan(self, scan_id: str) -> bool:
        """Resume a paused scan."""
        db_id = self._active_scans.get(scan_id)
        if not db_id:
            return False
        
        result = self.db.update_scan(db_id, {'status': 'running'})
        return result is not None
    
    def complete_scan(self, scan_id: str, wandb_link: Optional[str] = None) -> bool:
        """
        Mark a scan as completed.
        
        Args:
            scan_id: The scan ID to complete
            wandb_link: Optional W&B run link
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._active_scans.get(scan_id)
        if not db_id:
            return False
        
        update_data = {
            'status': 'completed',
            'completed_at': datetime.now()  # Use datetime object, not string
        }
        
        if wandb_link:
            update_data['wandb_link'] = wandb_link
        
        result = self.db.update_scan(db_id, update_data)
        
        if result:
            del self._active_scans[scan_id]
        
        return result is not None
    
    def fail_scan(self, scan_id: str, error_message: Optional[str] = None) -> bool:
        """
        Mark a scan as failed.
        
        Args:
            scan_id: The scan ID that failed
            error_message: Optional error message
            
        Returns:
            True if successful, False otherwise
        """
        db_id = self._active_scans.get(scan_id)
        if not db_id:
            return False
        
        update_data = {
            'status': 'failed',
            'completed_at': datetime.now()  # Use datetime object, not string
        }
        
        if error_message:
            update_data['extra_data'] = {'error': error_message}
        
        result = self.db.update_scan(db_id, update_data)
        
        if result:
            del self._active_scans[scan_id]
        
        return result is not None
    
    def abort_scan(self, scan_id: str) -> bool:
        """Mark a scan as aborted."""
        db_id = self._active_scans.get(scan_id)
        if not db_id:
            return False
        
        result = self.db.update_scan(db_id, {
            'status': 'aborted',
            'completed_at': datetime.now()  # Use datetime object, not string
        })
        
        if result:
            del self._active_scans[scan_id]
        
        return result is not None
    
    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Get scan data from database."""
        db_id = self._active_scans.get(scan_id)
        if db_id:
            return self.db.get_scan(db_id)
        return self.db.get_scan_by_scan_id(scan_id)
    
    def get_active_scans(self) -> List[Dict[str, Any]]:
        """Get all currently active scans."""
        return self.db.get_scans(status='running')[0]
    
    def get_scans_for_queue(self, queue_id: int) -> List[Dict[str, Any]]:
        """
        Get all scans associated with a queue.
        
        Args:
            queue_id: Database queue ID
            
        Returns:
            List of scan data dictionaries
        """
        if hasattr(self.db, 'get_scans_by_queue'):
            return self.db.get_scans_by_queue(queue_id)
        
        # Fallback: filter from all scans
        scans, _ = self.db.get_scans()
        return [s for s in scans if s.get('queue_id') == queue_id]
    
    def update_scan_duration(self, scan_id: str) -> bool:
        """Calculate and update scan duration."""
        scan = self.get_scan(scan_id)
        if not scan or not scan.get('started_at'):
            return False
        
        started = datetime.fromisoformat(scan['started_at'])
        duration = (datetime.now() - started).total_seconds()
        
        return self.db.update_scan(scan['id'], {'duration_seconds': duration}) is not None
    
    @staticmethod
    def serialize_scan_settings(scan_settings: 'ScanSettings') -> Dict[str, Any]:
        """
        Serialize a ScanSettings object to a dictionary.
        
        Args:
            scan_settings: PyBirch ScanSettings object
            
        Returns:
            Dictionary representation
        """
        data = {
            'project_name': scan_settings.project_name,
            'scan_name': scan_settings.scan_name,
            'scan_type': scan_settings.scan_type,
            'job_type': scan_settings.job_type,
        }
        
        if hasattr(scan_settings, 'scan_tree') and scan_settings.scan_tree:
            try:
                data['scan_tree'] = scan_settings.scan_tree.serialize()
            except Exception:
                pass
        
        if hasattr(scan_settings, 'extensions'):
            data['extensions'] = [ext.__class__.__name__ for ext in scan_settings.extensions]
        
        if hasattr(scan_settings, 'user_fields'):
            data['user_fields'] = scan_settings.user_fields
        
        if hasattr(scan_settings, 'additional_tags'):
            data['additional_tags'] = scan_settings.additional_tags
        
        return data
