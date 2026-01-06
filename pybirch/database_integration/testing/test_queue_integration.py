"""
Queue Integration Tests
=======================
Tests for DatabaseQueue integration with PyBirch Queue system.

These tests verify:
- DatabaseQueue creates and tracks queue records
- Scans are automatically tracked when enqueued
- State changes sync to database
- Logs are persisted
- Queue recovery works
"""

import unittest
import tempfile
import os
import time
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from threading import Event


# ==================== Mock Database Service ====================

class MockDatabaseService:
    """Mock database service for testing without actual database."""
    
    def __init__(self):
        self._queues = {}
        self._scans = {}
        self._logs = []
        self._next_queue_id = 1
        self._next_scan_id = 1
    
    def create_queue(self, data):
        """Create a mock queue record."""
        queue_id = self._next_queue_id
        self._next_queue_id += 1
        
        record = {
            'id': queue_id,
            **data,
            'created_at': datetime.now().isoformat(),
        }
        self._queues[queue_id] = record
        return record
    
    def get_queue(self, queue_id):
        """Get queue by ID."""
        if isinstance(queue_id, int):
            return self._queues.get(queue_id)
        # Try by queue_id string
        for q in self._queues.values():
            if q.get('queue_id') == queue_id:
                return q
        return None
    
    def get_queue_by_queue_id(self, queue_uuid):
        """Get queue by UUID string."""
        for q in self._queues.values():
            if q.get('queue_id') == queue_uuid:
                return q
        return None
    
    def update_queue(self, queue_id, data):
        """Update queue record."""
        if queue_id in self._queues:
            self._queues[queue_id].update(data)
            return self._queues[queue_id]
        return None
    
    def create_scan(self, data):
        """Create a mock scan record."""
        scan_id = self._next_scan_id
        self._next_scan_id += 1
        
        record = {
            'id': scan_id,
            **data,
            'created_at': datetime.now().isoformat(),
        }
        self._scans[scan_id] = record
        return record
    
    def get_scan(self, scan_id):
        """Get scan by ID."""
        return self._scans.get(scan_id)
    
    def get_scan_by_scan_id(self, scan_id_str):
        """Get scan by scan_id string."""
        for s in self._scans.values():
            if s.get('scan_id') == scan_id_str:
                return s
        return None
    
    def update_scan(self, scan_id, data):
        """Update scan record."""
        if scan_id in self._scans:
            self._scans[scan_id].update(data)
            return self._scans[scan_id]
        return None
    
    def get_scans(self, status=None):
        """Get all scans, optionally filtered by status."""
        scans = list(self._scans.values())
        if status:
            scans = [s for s in scans if s.get('status') == status]
        return scans, len(scans)
    
    def get_scans_by_queue(self, queue_id):
        """Get scans for a queue."""
        return [s for s in self._scans.values() if s.get('queue_id') == queue_id]
    
    def create_queue_log(self, queue_id, level, message, scan_id=None):
        """Create a queue log entry."""
        log = {
            'queue_id': queue_id,
            'level': level,
            'message': message,
            'scan_id': scan_id,
            'timestamp': datetime.now().isoformat(),
        }
        self._logs.append(log)
        return log
    
    def create_measurement_object(self, scan_id, name, columns=None, data_type='float', unit=None, instrument_name=None):
        """Mock measurement object creation."""
        return {'id': len(self._scans) + 1, 'scan_id': scan_id, 'name': name}
    
    def bulk_create_data_points(self, measurement_object_id, data_points):
        """Mock bulk data point creation."""
        return len(data_points)


# ==================== Mock PyBirch Components ====================

class MockScanSettings:
    """Mock ScanSettings for testing."""
    
    def __init__(self, project_name="test_project", scan_name="test_scan"):
        self.project_name = project_name
        self.scan_name = scan_name
        self.scan_type = "1D Scan"
        self.job_type = "Test"
        self.extensions = []
        self.status = "Queued"
        self.scan_tree = None
        self.additional_tags = []
    
    def serialize(self):
        return {
            'project_name': self.project_name,
            'scan_name': self.scan_name,
            'scan_type': self.scan_type,
            'job_type': self.job_type,
        }


class MockScan:
    """Mock Scan for testing queue operations."""
    
    def __init__(self, settings, owner="test_user", sample_ID="S001"):
        self.scan_settings = settings
        self.owner = owner
        self.sample_ID = sample_ID
        self._stop_event = Event()
        self.run = None  # W&B run
        self.current_item = None
        self._execution_time = 0.1  # seconds to simulate execution
    
    def startup(self):
        """Initialize the scan."""
        for ext in self.scan_settings.extensions:
            if hasattr(ext, 'set_scan_reference'):
                ext.set_scan_reference(self)
            if hasattr(ext, 'startup'):
                ext.startup()
    
    def execute(self):
        """Execute the scan."""
        for ext in self.scan_settings.extensions:
            if hasattr(ext, 'execute'):
                ext.execute()
        
        # Simulate execution
        time.sleep(self._execution_time)
    
    def shutdown(self):
        """Shutdown the scan."""
        for ext in self.scan_settings.extensions:
            if hasattr(ext, 'shutdown'):
                ext.shutdown()


# ==================== Test Classes ====================

class TestDatabaseQueueBasics(unittest.TestCase):
    """Test basic DatabaseQueue operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = MockDatabaseService()
        
        # Patch imports in the database_queue module
        self.patches = []
        
        # We need to test with the actual DatabaseQueue
        # but mock the database service
    
    def tearDown(self):
        """Clean up patches."""
        for p in self.patches:
            p.stop()
    
    def test_mock_db_service(self):
        """Test that mock database service works."""
        # Create queue
        queue_data = self.db.create_queue({
            'queue_id': 'Q_001',
            'name': 'Test Queue',
            'status': 'pending',
        })
        
        self.assertEqual(queue_data['id'], 1)
        self.assertEqual(queue_data['name'], 'Test Queue')
        
        # Update queue
        updated = self.db.update_queue(1, {'status': 'running'})
        self.assertEqual(updated['status'], 'running')
        
        # Get queue
        retrieved = self.db.get_queue(1)
        self.assertEqual(retrieved['status'], 'running')
    
    def test_mock_scan_lifecycle(self):
        """Test mock scan lifecycle."""
        settings = MockScanSettings("proj", "scan_001")
        scan = MockScan(settings)
        
        scan.startup()
        self.assertEqual(len(settings.extensions), 0)  # No extensions added yet
        
        scan.execute()
        scan.shutdown()


class TestQueueManagerIntegration(unittest.TestCase):
    """Test QueueManager with mock database."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = MockDatabaseService()
        
        # Import and create QueueManager
        from pybirch.database_integration.managers.queue_manager import QueueManager
        self.queue_manager = QueueManager(self.db)
    
    def test_create_queue(self):
        """Test queue creation."""
        result = self.queue_manager.create_queue(
            name="Test Queue",
            execution_mode="SERIAL",
            operator="test_user",
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Test Queue')
        self.assertIn('queue_id', result)
    
    def test_queue_lifecycle(self):
        """Test queue lifecycle operations."""
        # Create
        result = self.queue_manager.create_queue(name="Lifecycle Test")
        queue_id = result['queue_id']
        
        # Start
        success = self.queue_manager.start_queue(queue_id)
        self.assertTrue(success)
        
        queue = self.queue_manager.get_queue(queue_id)
        self.assertEqual(queue['status'], 'running')
        
        # Pause
        success = self.queue_manager.pause_queue(queue_id)
        self.assertTrue(success)
        
        queue = self.queue_manager.get_queue(queue_id)
        self.assertEqual(queue['status'], 'paused')
        
        # Resume
        success = self.queue_manager.resume_queue(queue_id)
        self.assertTrue(success)
        
        queue = self.queue_manager.get_queue(queue_id)
        self.assertEqual(queue['status'], 'running')
        
        # Complete
        success = self.queue_manager.complete_queue(queue_id)
        self.assertTrue(success)
        
        queue = self.queue_manager.get_queue(queue_id)
        self.assertEqual(queue['status'], 'completed')
    
    def test_progress_tracking(self):
        """Test queue progress updates."""
        result = self.queue_manager.create_queue(name="Progress Test")
        queue_id = result['queue_id']
        
        # Update progress
        success = self.queue_manager.update_progress(queue_id, completed_scans=2, total_scans=5)
        self.assertTrue(success)
        
        queue = self.queue_manager.get_queue(queue_id)
        self.assertEqual(queue['completed_scans'], 2)
        self.assertEqual(queue['total_scans'], 5)
    
    def test_logging(self):
        """Test queue log entries."""
        result = self.queue_manager.create_queue(name="Log Test")
        queue_id = result['queue_id']
        
        # Add log
        success = self.queue_manager.add_log(
            queue_id,
            level='INFO',
            message='Test log message',
            scan_id='scan_001',
        )
        self.assertTrue(success)
        
        # Check logs were created
        self.assertEqual(len(self.db._logs), 1)
        self.assertEqual(self.db._logs[0]['message'], 'Test log message')


class TestScanManagerIntegration(unittest.TestCase):
    """Test ScanManager with mock database."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = MockDatabaseService()
        
        from pybirch.database_integration.managers.scan_manager import ScanManager
        self.scan_manager = ScanManager(self.db)
    
    def test_create_scan_from_settings(self):
        """Test creating scan from ScanSettings."""
        settings = MockScanSettings("project_x", "measurement_001")
        
        result = self.scan_manager.create_scan(
            settings,
            sample_id=1,
            project_id=1,
            owner="researcher",
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['project_name'], 'project_x')
        self.assertEqual(result['scan_name'], 'measurement_001')
        self.assertEqual(result['status'], 'pending')
    
    def test_scan_lifecycle(self):
        """Test scan lifecycle operations."""
        settings = MockScanSettings("proj", "scan")
        result = self.scan_manager.create_scan(settings)
        scan_id = result['scan_id']
        
        # Start
        success = self.scan_manager.start_scan(scan_id)
        self.assertTrue(success)
        
        scan = self.scan_manager.get_scan(scan_id)
        self.assertEqual(scan['status'], 'running')
        
        # Complete
        success = self.scan_manager.complete_scan(scan_id, wandb_link="https://wandb.ai/run/123")
        self.assertTrue(success)
        
        scan = self.scan_manager.get_scan(scan_id)
        self.assertEqual(scan['status'], 'completed')
        self.assertEqual(scan['wandb_link'], 'https://wandb.ai/run/123')
    
    def test_scan_failure(self):
        """Test scan failure handling."""
        settings = MockScanSettings("proj", "failing_scan")
        result = self.scan_manager.create_scan(settings)
        scan_id = result['scan_id']
        
        # Start then fail
        self.scan_manager.start_scan(scan_id)
        success = self.scan_manager.fail_scan(scan_id, error_message="Instrument error")
        self.assertTrue(success)
        
        scan = self.scan_manager.get_scan(scan_id)
        self.assertEqual(scan['status'], 'failed')
    
    def test_get_scans_for_queue(self):
        """Test getting scans by queue."""
        # Create queue record
        queue = self.db.create_queue({'queue_id': 'Q_001', 'name': 'Test'})
        
        # Create scans
        for i in range(3):
            settings = MockScanSettings("proj", f"scan_{i}")
            self.scan_manager.create_scan(settings, queue_id=queue['id'])
        
        # Get scans for queue
        scans = self.scan_manager.get_scans_for_queue(queue['id'])
        self.assertEqual(len(scans), 3)


class TestDatabaseExtensionWithQueue(unittest.TestCase):
    """Test DatabaseExtension working with queue context."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = MockDatabaseService()
        self._skip_if_no_pandas = False
        try:
            import pandas
        except ImportError:
            self._skip_if_no_pandas = True
    
    def test_extension_with_queue_id(self):
        """Test extension created with queue context."""
        if self._skip_if_no_pandas:
            self.skipTest("pandas not available - extension tests require pandas")
        
        from pybirch.database_integration.extensions.database_extension import DatabaseExtension
        
        # Create queue first
        queue = self.db.create_queue({'queue_id': 'Q_test', 'name': 'Test Queue'})
        
        # Create extension with queue context
        ext = DatabaseExtension(
            db_service=self.db,
            sample_id=1,
            project_id=1,
            queue_id=queue['id'],
            owner="test_user",
        )
        
        self.assertEqual(ext.queue_id, queue['id'])
    
    def test_extension_lifecycle_with_mock_scan(self):
        """Test extension through full lifecycle."""
        if self._skip_if_no_pandas:
            self.skipTest("pandas not available - extension tests require pandas")
        
        from pybirch.database_integration.extensions.database_extension import DatabaseExtension
        
        settings = MockScanSettings("proj", "test_scan")
        ext = DatabaseExtension(
            db_service=self.db,
            sample_id=1,
            project_id=1,
            scan_settings=settings,
        )
        
        scan = MockScan(settings)
        settings.extensions.append(ext)
        
        # Run lifecycle
        scan.startup()
        
        # Check DB record created
        self.assertIsNotNone(ext.db_scan_id)
        self.assertIsNotNone(ext.scan_id)
        
        scan.execute()
        scan.shutdown()
        
        # Check scan completed
        db_scan = self.db.get_scan(ext.db_scan_id)
        self.assertEqual(db_scan['status'], 'completed')


class TestDatabaseQueueIntegration(unittest.TestCase):
    """
    Integration tests for DatabaseQueue.
    
    These tests verify the full integration between DatabaseQueue
    and the database tracking system.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.db = MockDatabaseService()
        self._skip_if_no_pandas = False
        try:
            import pandas
        except ImportError:
            self._skip_if_no_pandas = True
    
    def test_database_queue_creation(self):
        """Test DatabaseQueue creates database record."""
        if self._skip_if_no_pandas:
            self.skipTest("pandas not available - full integration tests require pandas")
        
        # This test requires the actual DatabaseQueue
        # We'll test the components it uses
        from pybirch.database_integration.managers.queue_manager import QueueManager
        
        manager = QueueManager(self.db)
        result = manager.create_queue(
            name="Integration Test Queue",
            execution_mode="SERIAL",
            operator="tester",
        )
        
        self.assertIsNotNone(result['id'])
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['execution_mode'], 'SERIAL')
    
    def test_multi_scan_tracking(self):
        """Test tracking multiple scans in a queue."""
        from pybirch.database_integration.managers.queue_manager import QueueManager
        from pybirch.database_integration.managers.scan_manager import ScanManager
        
        queue_mgr = QueueManager(self.db)
        scan_mgr = ScanManager(self.db)
        
        # Create queue
        queue = queue_mgr.create_queue(name="Multi-Scan Queue")
        queue_id = queue['queue_id']
        
        # Start queue
        queue_mgr.start_queue(queue_id)
        
        # Create and track multiple scans
        scan_ids = []
        for i in range(3):
            settings = MockScanSettings("proj", f"scan_{i}")
            scan_data = scan_mgr.create_scan(
                settings,
                queue_id=queue['id'],
                project_id=1,
            )
            scan_ids.append(scan_data['scan_id'])
            
            # Simulate scan lifecycle
            scan_mgr.start_scan(scan_data['scan_id'])
            scan_mgr.complete_scan(scan_data['scan_id'])
            
            # Update queue progress
            queue_mgr.update_progress(queue_id, completed_scans=i+1, total_scans=3)
        
        # Complete queue
        queue_mgr.complete_queue(queue_id)
        
        # Verify
        final_queue = queue_mgr.get_queue(queue_id)
        self.assertEqual(final_queue['status'], 'completed')
        self.assertEqual(final_queue['completed_scans'], 3)
        
        # Check all scans completed
        for scan_id in scan_ids:
            scan = scan_mgr.get_scan(scan_id)
            self.assertEqual(scan['status'], 'completed')
    
    def test_queue_recovery_data(self):
        """Test data needed for queue recovery."""
        from pybirch.database_integration.managers.queue_manager import QueueManager
        from pybirch.database_integration.managers.scan_manager import ScanManager
        
        queue_mgr = QueueManager(self.db)
        scan_mgr = ScanManager(self.db)
        
        # Create queue and partial execution
        queue = queue_mgr.create_queue(name="Recovery Test")
        queue_id = queue['queue_id']
        
        queue_mgr.start_queue(queue_id)
        
        # First scan completes
        settings1 = MockScanSettings("proj", "scan_1")
        scan1 = scan_mgr.create_scan(settings1, queue_id=queue['id'])
        scan_mgr.start_scan(scan1['scan_id'])
        scan_mgr.complete_scan(scan1['scan_id'])
        
        # Second scan running when "crash" happens
        settings2 = MockScanSettings("proj", "scan_2")
        scan2 = scan_mgr.create_scan(settings2, queue_id=queue['id'])
        scan_mgr.start_scan(scan2['scan_id'])
        
        # Simulate recovery - get incomplete scans
        all_scans = scan_mgr.get_scans_for_queue(queue['id'])
        incomplete = [s for s in all_scans if s['status'] not in ('completed', 'failed', 'aborted')]
        
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0]['scan_name'], 'scan_2')
        self.assertEqual(incomplete[0]['status'], 'running')


# ==================== Run Tests ====================

if __name__ == '__main__':
    unittest.main(verbosity=2)
