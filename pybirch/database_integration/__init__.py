"""
PyBirch Database Integration Layer
==================================
This module provides integration between PyBirch's measurement framework
and the database system for persistent storage and tracking.

The integration layer enables:
- Automatic persistence of scan data to the database
- Real-time status synchronization via WebSocket
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
    
    # Real-time WebSocket updates (requires flask-socketio)
    from pybirch.database_integration.sync import ScanUpdateServer, init_socketio
    socketio = init_socketio(app)
    server = ScanUpdateServer(socketio)
    server.broadcast_scan_status('SCAN_001', 'running', progress=0.5)
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

# Sync module for WebSocket support (optional flask-socketio)
try:
    from .sync.websocket_server import ScanUpdateServer, init_socketio, get_socketio
    from .sync.event_handlers import (
        ScanEventHandler,
        QueueEventHandler,
        InstrumentEventHandler,
        setup_all_handlers,
    )
except ImportError:
    ScanUpdateServer = None
    init_socketio = None
    get_socketio = None
    ScanEventHandler = None
    QueueEventHandler = None
    InstrumentEventHandler = None
    setup_all_handlers = None

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
    # Sync/WebSocket
    'ScanUpdateServer',
    'init_socketio',
    'get_socketio',
    'ScanEventHandler',
    'QueueEventHandler',
    'InstrumentEventHandler',
    'setup_all_handlers',]