"""
Database Integration Tests
==========================
Tests for verifying the database integration layer works correctly
with PyBirch scans and fake instruments.
"""

import os
import sys
import unittest
import tempfile
import numpy as np
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Import test utilities
from pybirch.database_integration.testing import (
    FakeMultimeter,
    FakeSpectrometer,
    FakeLockin,
    FakeStage,
    create_test_instruments,
)

# Import database integration
from pybirch.database_integration import (
    DatabaseExtension,
    DatabaseQueueExtension,
    ScanManager,
    QueueManager,
    EquipmentManager,
    DataManager,
)

# Import database service
try:
    from database.services import DatabaseService
    from database.models import Base
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    print("Warning: Database module not available, some tests will be skipped")


class MockScanSettings:
    """Mock ScanSettings for testing without full PyBirch."""
    
    def __init__(self, 
                 project_name="test_project",
                 scan_name="test_scan",
                 scan_type="1D Scan",
                 job_type="Raman"):
        self.project_name = project_name
        self.scan_name = scan_name
        self.scan_type = scan_type
        self.job_type = job_type
        self.additional_tags = ["test", "integration"]
        self.extensions = []
        self.status = "Queued"
        self.wandb_link = ""
        self.user_fields = {}
        self.start_date = ""
        self.end_date = ""
    
    def serialize(self):
        return {
            "project_name": self.project_name,
            "scan_name": self.scan_name,
            "scan_type": self.scan_type,
            "job_type": self.job_type,
            "additional_tags": self.additional_tags,
            "status": self.status,
            "user_fields": self.user_fields,
        }


class MockScan:
    """Mock Scan for testing without full PyBirch."""
    
    def __init__(self, scan_settings: MockScanSettings, owner: str = "test_user"):
        self.scan_settings = scan_settings
        self.owner = owner
        self.extensions = scan_settings.extensions
        self.run = None  # Mock wandb run


class TestFakeInstruments(unittest.TestCase):
    """Test the fake instruments work correctly."""
    
    def test_fake_multimeter(self):
        """Test FakeMultimeter generates valid data."""
        dmm = FakeMultimeter("Test_DMM")
        dmm.connect()
        
        self.assertTrue(dmm.status)
        self.assertEqual(len(dmm.data_columns), 2)
        
        # Perform measurement
        data = dmm.perform_measurement()
        self.assertEqual(data.shape, (1, 2))
        
        # Check DataFrame
        df = dmm.measurement_df()
        self.assertEqual(len(df.columns), 2)
        self.assertEqual(len(df), 1)
    
    def test_fake_spectrometer(self):
        """Test FakeSpectrometer generates spectrum data."""
        spec = FakeSpectrometer("Test_Spec", num_pixels=100)
        spec.connect()
        
        data = spec.perform_measurement()
        self.assertEqual(data.shape[1], 100)
        
        # Check peaks are present
        self.assertTrue(np.max(data) > 100)  # Should have peaks
    
    def test_fake_lockin(self):
        """Test FakeLockin generates X, Y, R, Theta data."""
        lockin = FakeLockin("Test_Lockin")
        lockin.connect()
        
        data = lockin.perform_measurement()
        self.assertEqual(data.shape, (1, 4))
        
        # X, Y, R, Theta
        x, y, r, theta = data[0]
        self.assertAlmostEqual(r, np.sqrt(x**2 + y**2), places=10)
    
    def test_fake_stage(self):
        """Test FakeStage movement."""
        stage = FakeStage("Test_Stage", axis="X")
        stage.connect()
        
        # Initial position
        self.assertAlmostEqual(stage.position, 0.0, places=2)
        
        # Move to position
        stage.move_to(10.0)
        self.assertAlmostEqual(stage.position, 10.0, places=1)
        
        # Check limits
        stage.move_to(100.0)  # Beyond max
        self.assertLessEqual(stage.position, 50.0)  # Should be clamped


@unittest.skipUnless(HAS_DATABASE, "Database module not available")
class TestDatabaseIntegration(unittest.TestCase):
    """Test database integration with mock scans."""
    
    @classmethod
    def setUpClass(cls):
        """Create a temporary database for testing."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_integration.db")
        cls.db = DatabaseService(cls.db_path)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up temporary database."""
        import shutil
        try:
            shutil.rmtree(cls.temp_dir)
        except Exception:
            pass
    
    def test_scan_manager_create_scan(self):
        """Test ScanManager creates scans correctly."""
        scan_mgr = ScanManager(self.db)
        
        settings = MockScanSettings(
            project_name="TestProject",
            scan_name="TestScan001"
        )
        
        db_scan = scan_mgr.create_scan(settings, owner="test_user")
        
        self.assertIsNotNone(db_scan)
        self.assertIn('id', db_scan)
        self.assertIn('scan_id', db_scan)
        self.assertEqual(db_scan['status'], 'pending')
    
    def test_scan_lifecycle(self):
        """Test full scan lifecycle: create -> start -> complete."""
        scan_mgr = ScanManager(self.db)
        
        settings = MockScanSettings(scan_name="LifecycleTest")
        
        # Create
        db_scan = scan_mgr.create_scan(settings, owner="test_user")
        scan_id = db_scan['scan_id']
        
        # Start
        scan_mgr.start_scan(scan_id)
        scan = scan_mgr.get_scan(scan_id)
        self.assertEqual(scan['status'], 'running')
        
        # Complete
        scan_mgr.complete_scan(scan_id, wandb_link="https://wandb.ai/test")
        scan = scan_mgr.get_scan(scan_id)
        self.assertEqual(scan['status'], 'completed')
        self.assertEqual(scan['wandb_link'], "https://wandb.ai/test")
    
    def test_data_manager_save_dataframe(self):
        """Test DataManager saves DataFrame data correctly."""
        # First create a scan
        scan = self.db.create_scan({
            'scan_name': 'DataTest',
            'scan_type': 'test',
            'owner': 'test_user',
        })
        scan_id = scan['id']
        
        data_mgr = DataManager(self.db, buffer_size=5)
        
        # Save some data
        df = pd.DataFrame({
            'x': [1.0, 2.0, 3.0],
            'y': [10.0, 20.0, 30.0],
        })
        
        count = data_mgr.save_dataframe(
            scan_id, 
            'test_measurement', 
            df,
            instrument_name='TestInstrument'
        )
        
        self.assertEqual(count, 3)
        
        # Flush and verify
        data_mgr.flush(scan_id)
        
        # Get data back
        retrieved = data_mgr.get_data(scan_id, 'test_measurement')
        self.assertEqual(len(retrieved), 3)
    
    def test_database_extension(self):
        """Test DatabaseExtension integrates with mock scan."""
        # Create extension
        extension = DatabaseExtension(
            self.db,
            owner="extension_test_user"
        )
        
        # Create mock scan
        settings = MockScanSettings(
            project_name="ExtensionTest",
            scan_name="ExtScan001"
        )
        settings.extensions = [extension]
        scan = MockScan(settings)
        
        # Simulate scan lifecycle
        extension.set_scan_reference(scan)
        extension.startup()
        
        self.assertIsNotNone(extension.db_scan_id)
        self.assertIsNotNone(extension.scan_id)
        
        extension.execute()
        
        # Save some data
        df = pd.DataFrame({'value': [1, 2, 3, 4, 5]})
        extension.save_data(df, 'test_measurement')
        
        # Complete
        extension.shutdown()
        
        # Verify scan is completed
        scan_info = extension.get_scan_info()
        self.assertEqual(scan_info['status'], 'completed')
    
    def test_equipment_manager(self):
        """Test EquipmentManager registers instruments correctly."""
        equip_mgr = EquipmentManager(self.db)
        
        # Create fake instrument
        dmm = FakeMultimeter("DB_Test_DMM")
        dmm.connect()
        
        # Register
        equipment = equip_mgr.register_instrument(dmm)
        
        self.assertIsNotNone(equipment)
        self.assertEqual(equipment['name'], 'DB_Test_DMM')
        
        # Update status
        result = equip_mgr.update_status('DB_Test_DMM', 'active', 'Running measurements')
        self.assertTrue(result)
    
    def test_queue_manager(self):
        """Test QueueManager creates and manages queues."""
        queue_mgr = QueueManager(self.db)
        
        # Create queue
        db_queue = queue_mgr.create_queue(
            name="TestQueue",
            total_scans=5,
            operator="test_operator"
        )
        
        self.assertIsNotNone(db_queue)
        queue_id = db_queue['queue_id']
        
        # Start queue
        queue_mgr.start_queue(queue_id)
        queue = queue_mgr.get_queue(queue_id)
        self.assertEqual(queue['status'], 'running')
        
        # Update progress
        queue_mgr.update_progress(queue_id, completed_scans=2)
        
        # Complete queue
        queue_mgr.complete_queue(queue_id)
        queue = queue_mgr.get_queue(queue_id)
        self.assertEqual(queue['status'], 'completed')


@unittest.skipUnless(HAS_DATABASE, "Database module not available")
class TestIntegrationWithFakeInstruments(unittest.TestCase):
    """Test database integration with fake instruments."""
    
    @classmethod
    def setUpClass(cls):
        """Create a temporary database for testing."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_full_integration.db")
        cls.db = DatabaseService(cls.db_path)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up temporary database."""
        import shutil
        try:
            shutil.rmtree(cls.temp_dir)
        except Exception:
            pass
    
    def test_full_measurement_flow(self):
        """Test complete measurement flow with fake instruments."""
        # Create instruments
        dmm = FakeMultimeter("IntegTest_DMM")
        stage = FakeStage("IntegTest_Stage", axis="X")
        
        dmm.connect()
        stage.connect()
        
        # Create database extension
        extension = DatabaseExtension(
            self.db,
            owner="integration_test"
        )
        
        # Create mock scan
        settings = MockScanSettings(
            project_name="FullIntegration",
            scan_name="FullTest001",
            scan_type="Line Scan",
            job_type="IV Measurement"
        )
        settings.extensions = [extension]
        scan = MockScan(settings)
        
        # Start scan
        extension.set_scan_reference(scan)
        extension.startup()
        extension.execute()
        
        # Simulate line scan
        positions = np.linspace(0, 10, 10)
        for pos in positions:
            stage.move_to(pos)
            
            # Take measurement
            measurement = dmm.measurement_df()
            measurement['X_position (mm)'] = stage.position
            
            extension.save_data(measurement, f'{dmm.name}_measurement')
        
        # Complete scan
        extension.shutdown()
        
        # Verify data was saved
        scan_info = extension.get_scan_info()
        self.assertEqual(scan_info['status'], 'completed')
        
        # Get data count
        data_count = extension.data_manager.get_data_count(extension.db_scan_id)
        self.assertEqual(data_count, 10)
    
    def test_multi_instrument_measurement(self):
        """Test measurement with multiple instruments."""
        # Create instruments
        instruments = create_test_instruments()
        
        for inst in instruments.values():
            if hasattr(inst, 'connect'):
                inst.connect()
        
        # Create extension
        extension = DatabaseExtension(
            self.db,
            owner="multi_instrument_test"
        )
        
        settings = MockScanSettings(
            project_name="MultiInstrument",
            scan_name="MultiTest001"
        )
        settings.extensions = [extension]
        scan = MockScan(settings)
        
        extension.set_scan_reference(scan)
        extension.startup()
        extension.execute()
        
        # Take measurements from multiple instruments
        for name, inst in instruments.items():
            if hasattr(inst, 'measurement_df'):
                df = inst.measurement_df()
                extension.save_data(df, f'{name}_data')
        
        extension.shutdown()
        
        # Verify completion
        scan_info = extension.get_scan_info()
        self.assertEqual(scan_info['status'], 'completed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
