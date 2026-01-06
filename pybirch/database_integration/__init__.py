"""
PyBirch Database Integration Layer
==================================
This module provides integration between PyBirch's measurement framework
and the database system for persistent storage and tracking.

The integration layer enables:
- Automatic persistence of scan data to the database
- Real-time status synchronization
- Equipment registry and settings management
- Buffered data writes for performance
- Queue-level tracking with multi-scan management

Usage:
    from database.services import DatabaseService
    from pybirch.database_integration import DatabaseExtension, DatabaseQueue
    
    db = DatabaseService('path/to/database.db')
    
    # Single scan with database tracking
    extension = DatabaseExtension(db, sample_id=1, project_id=1)
    scan = Scan(settings, sample, extensions=[extension])
    scan.startup()
    scan.execute()
    
    # Queue with automatic database tracking
    queue = DatabaseQueue(QID="my_queue", db_service=db, project_id=1)
    queue.enqueue(scan1)
    queue.enqueue(scan2)
    queue.start()
"""

from .managers.scan_manager import ScanManager
from .managers.queue_manager import QueueManager
from .managers.equipment_manager import EquipmentManager

# DataManager requires pandas - import conditionally
try:
    from .managers.data_manager import DataManager
except ImportError:
    DataManager = None  # Will be None if pandas not available

# Extensions may require pandas via DataManager
try:
    from .extensions.database_extension import DatabaseExtension, DatabaseQueueExtension
    from .extensions.database_queue import DatabaseQueue
except ImportError:
    DatabaseExtension = None
    DatabaseQueueExtension = None
    DatabaseQueue = None

__all__ = [
    # Managers
    'ScanManager',
    'QueueManager', 
    'EquipmentManager',
    'DataManager',
    # Extensions
    'DatabaseExtension',
    'DatabaseQueueExtension',
    'DatabaseQueue',
]
