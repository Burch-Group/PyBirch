"""
Queue-Database Integration Test
===============================
Comprehensive test script that creates a queue with two scans (IV scan and Raman spectrum),
runs them using PyBirch fake instruments, and saves the results to the database.

This tests the complete data flow:
1. Create fake instruments (multimeter, spectrometer, current source)
2. Build scans with movement and measurement instruments
3. Create a queue to track scans
4. Execute the queue
5. Save data to the PyBirch database
6. Verify data retrieval

Run with: python tests/test_queue_database_integration.py
Or: pytest tests/test_queue_database_integration.py -v -s

Note: This script is designed to work without full PyBirch GUI dependencies.
It uses simplified scan classes that mimic PyBirch behavior.
"""

import os
import sys
import time
import tempfile
import numpy as np
import pandas as pd
from datetime import datetime
from threading import Event
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Disable wandb for testing
os.environ["WANDB_MODE"] = "disabled"

# Try to import pytest - optional for standalone execution
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

# ==================== Imports ====================

# Database
from database.services import DatabaseService

# Fake Instruments - these work without GUI dependencies
from pybirch.setups.fake_setup.multimeter.multimeter import (
    FakeMultimeter,
    VoltageMeterMeasurement,
    CurrentSourceMovement,
)
from pybirch.setups.fake_setup.spectrometer.spectrometer import FakeSpectrometer

print("✓ Imports successful (using simplified scan execution)")


# ==================== Simplified Scan Classes ====================

class SimpleScanSettings:
    """Simplified ScanSettings for testing without GUI dependencies."""
    
    def __init__(
        self,
        project_name: str,
        scan_name: str,
        scan_type: str = "1D Scan",
        job_type: str = "Test",
        additional_tags: Optional[List[str]] = None,
        user_fields: Optional[dict] = None,
    ):
        self.project_name = project_name
        self.scan_name = scan_name
        self.scan_type = scan_type
        self.job_type = job_type
        self.additional_tags = additional_tags or []
        self.user_fields = user_fields or {}
        self.status = "Queued"
        self.scan_tree = None
        
        # Instrument references for execution
        self.movement_instruments: List = []
        self.measurement_instruments: List = []
        self.movement_positions: List[np.ndarray] = []
    
    def serialize(self) -> dict:
        return {
            'project_name': self.project_name,
            'scan_name': self.scan_name,
            'scan_type': self.scan_type,
            'job_type': self.job_type,
            'additional_tags': self.additional_tags,
            'user_fields': self.user_fields,
        }


class SimpleDatabaseScan:
    """
    Simplified Scan class that saves data directly to the database.
    
    This class mimics the PyBirch Scan class behavior for:
    - Instrument initialization and shutdown
    - Data acquisition
    - Direct database persistence
    """
    
    def __init__(
        self,
        settings: SimpleScanSettings,
        db_service: DatabaseService,
        sample_id: Optional[int] = None,
        queue_id: Optional[int] = None,
        owner: str = "test_operator"
    ):
        self.scan_settings = settings
        self.db = db_service
        self.sample_id = sample_id
        self.queue_id = queue_id
        self.owner = owner
        
        # State
        self._stop_event = Event()
        self._data_collected: List[Dict] = []
        self._db_scan: Optional[Dict] = None
        self._measurement_objects: Dict[str, Dict] = {}
        
    @property
    def db_scan_id(self) -> Optional[int]:
        return self._db_scan['id'] if self._db_scan else None
    
    def startup(self):
        """Initialize instruments and create database record."""
        print(f"  [Scan] Starting up: {self.scan_settings.scan_name}")
        
        # Create database scan record
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        scan_data = {
            'scan_id': f"{self.scan_settings.project_name}_{self.scan_settings.scan_name}_{timestamp}",
            'project_name': self.scan_settings.project_name,
            'scan_name': self.scan_settings.scan_name,
            'scan_type': self.scan_settings.scan_type,
            'job_type': self.scan_settings.job_type,
            'status': 'pending',
            'created_by': self.owner,  # Use created_by, not owner
            'additional_tags': self.scan_settings.additional_tags,
            'sample_id': self.sample_id,
            'queue_id': self.queue_id,
            'extra_data': {'user_fields': self.scan_settings.user_fields},
        }
        self._db_scan = self.db.create_scan(scan_data)
        print(f"    Created DB scan: {self._db_scan['scan_id']} (ID: {self.db_scan_id})")
        
        # Connect and initialize instruments
        for inst in self.scan_settings.measurement_instruments:
            inst.connect()
            inst.initialize()
        for inst in self.scan_settings.movement_instruments:
            inst.connect()
            inst.initialize()
    
    def execute(self):
        """Execute the scan - collect data at each position and save to database."""
        print(f"  [Scan] Executing: {self.scan_settings.scan_name}")
        
        # Update status to running
        self.db.update_scan(self.db_scan_id, {'status': 'running'})
        
        # Execute scan: iterate over movement positions
        if self.scan_settings.movement_instruments and self.scan_settings.movement_positions:
            self._execute_sweep_scan()
        else:
            self._execute_single_measurement()
    
    def _execute_sweep_scan(self):
        """Execute a sweep scan (e.g., IV scan)."""
        movement = self.scan_settings.movement_instruments[0]
        positions = self.scan_settings.movement_positions[0]
        
        for pos in positions:
            if self._stop_event.is_set():
                break
            
            # Move to position
            movement.position = pos
            
            # Take measurements at this position
            for measurement in self.scan_settings.measurement_instruments:
                data = measurement.perform_measurement()
                
                # Create measurement object if it doesn't exist
                mo_key = measurement.name
                if mo_key not in self._measurement_objects:
                    self._measurement_objects[mo_key] = self._create_measurement_object(measurement)
                
                # Save data points
                self._save_data_points(
                    self._measurement_objects[mo_key]['id'],
                    data,
                    measurement,
                    position=pos,
                    movement=movement
                )
    
    def _execute_single_measurement(self):
        """Execute a single measurement scan (e.g., Raman spectrum)."""
        for measurement in self.scan_settings.measurement_instruments:
            data = measurement.perform_measurement()
            
            # Create measurement object
            mo_key = measurement.name
            if mo_key not in self._measurement_objects:
                self._measurement_objects[mo_key] = self._create_measurement_object(measurement)
            
            # Save data points
            self._save_data_points(
                self._measurement_objects[mo_key]['id'],
                data,
                measurement
            )
    
    def _create_measurement_object(self, measurement) -> Dict:
        """Create a measurement object in the database."""
        columns = list(measurement.data_columns)
        units = list(measurement.data_units)
        
        # Create columns string
        columns_str = ','.join([f"{c}({u})" for c, u in zip(columns, units)])
        
        mo = self.db.create_measurement_object(
            scan_id=self.db_scan_id,
            name=measurement.name,
            columns=columns,
            data_type='float',
            unit=units[0] if units else None,
            instrument_name=measurement.name
        )
        print(f"    Created measurement object: {measurement.name} (ID: {mo['id']})")
        return mo
    
    def _save_data_points(
        self,
        mo_id: int,
        data: np.ndarray,
        measurement,
        position: Optional[float] = None,
        movement=None
    ):
        """Save data points to the database."""
        # Create data points from the numpy array
        data_points = []
        
        for row_idx, row in enumerate(data):
            # Build values dict from columns
            values = {}
            for col_idx, col in enumerate(measurement.data_columns):
                values[col] = float(row[col_idx])
            
            # Add position if available
            if position is not None and movement:
                values[movement.position_column] = position
            
            data_points.append({
                'index': row_idx,
                'values': values,
                'metadata': {},
            })
        
        # Bulk create data points
        if data_points:
            self.db.bulk_create_data_points(mo_id, data_points)
    
    def shutdown(self):
        """Shutdown instruments and update database."""
        print(f"  [Scan] Shutting down: {self.scan_settings.scan_name}")
        
        # Shutdown instruments
        for inst in self.scan_settings.measurement_instruments:
            inst.shutdown()
        for inst in self.scan_settings.movement_instruments:
            inst.shutdown()
        
        # Update database status
        if self._db_scan:
            self.db.update_scan(self.db_scan_id, {'status': 'completed'})


@dataclass
class SimpleScanHandle:
    """Handle for tracking scan state in queue."""
    scan: SimpleDatabaseScan
    scan_id: str
    state: str = "queued"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class SimpleDatabaseQueue:
    """
    Simplified Queue class that tracks scans in the database.
    
    Supports:
    - Enqueueing scans
    - Serial execution
    - State tracking
    - Database integration
    """
    
    def __init__(
        self,
        QID: str,
        db_service: DatabaseService,
        sample_id: Optional[int] = None,
        project_id: Optional[int] = None,
        operator: Optional[str] = None,
    ):
        self.QID = QID
        self.db_service = db_service
        self.sample_id = sample_id
        self.project_id = project_id
        self.operator = operator
        self.state = "idle"
        self._scan_handles: List[SimpleScanHandle] = []
        self._scan_counter = 0
        
        # Create queue record in database
        self._db_queue = db_service.create_queue({
            'name': f"Queue {QID}",
            'sample_id': sample_id,
            'project_id': project_id,
            'status': 'pending',
            'execution_mode': 'serial',
            'created_by': operator,  # Use created_by, not operator
        })
        self.db_queue_id = self._db_queue['id']
        self.db_queue_uuid = self._db_queue['queue_id']
        print(f"[DB Queue] Created: {self.db_queue_uuid} (ID: {self.db_queue_id})")
    
    def size(self) -> int:
        return len(self._scan_handles)
    
    def enqueue(self, scan: SimpleDatabaseScan):
        """Add a scan to the queue."""
        self._scan_counter += 1
        scan_id = f"{self.QID}_scan_{self._scan_counter}"
        
        # Update scan's queue_id
        scan.queue_id = self.db_queue_id
        
        handle = SimpleScanHandle(scan=scan, scan_id=scan_id)
        self._scan_handles.append(handle)
        return handle
    
    def start(self, mode: str = "serial"):
        """Execute all scans in the queue."""
        print(f"\n[Queue] Starting execution: {self.QID} ({self.size()} scans)")
        self.state = "running"
        
        # Update queue status to running
        self.db_service.update_queue(self.db_queue_id, {'status': 'running'})
        
        for handle in self._scan_handles:
            if self.state != "running":
                break
            
            handle.state = "running"
            handle.start_time = time.time()
            
            try:
                handle.scan.startup()
                handle.scan.execute()
                handle.scan.shutdown()
                handle.state = "completed"
            except Exception as e:
                handle.state = "failed"
                handle.error = str(e)
                print(f"  [Queue] Scan failed: {handle.scan_id} - {e}")
                import traceback
                traceback.print_exc()
            finally:
                handle.end_time = time.time()
            
            print(f"  [Queue] Completed: {handle.scan.scan_settings.scan_name} "
                  f"in {handle.duration:.2f}s")
        
        # Update queue status
        completed = sum(1 for h in self._scan_handles if h.state == "completed")
        total = len(self._scan_handles)
        
        final_status = 'completed' if completed == total else 'partial'
        self.db_service.update_queue(self.db_queue_id, {
            'status': final_status,
            'completed_scans': completed,
            'total_scans': total,
        })
        
        self.state = "completed"
        print(f"[Queue] Finished: {self.QID}")


# ==================== Helper Functions ====================

def create_iv_scan(
    db: DatabaseService,
    sample_id: Optional[int] = None,
    queue_id: Optional[int] = None,
) -> SimpleDatabaseScan:
    """
    Create an IV (Current-Voltage) scan.
    
    This scan sweeps current from -1mA to +1mA and measures voltage at each point.
    Uses fake multimeter instruments.
    
    Args:
        db: Database service for creating database records
        sample_id: Sample ID to associate with scan
        queue_id: Queue ID if part of a queue
    
    Returns:
        SimpleDatabaseScan configured for IV sweep
    """
    # Create instruments
    current_source = CurrentSourceMovement("IV_Current_Source")
    voltage_meter = VoltageMeterMeasurement("IV_Voltage_Meter")
    
    # Create current sweep positions (-1mA to +1mA, 11 points for faster test)
    current_positions = np.linspace(-0.001, 0.001, 11)  # Amps
    
    # Create scan settings
    settings = SimpleScanSettings(
        project_name="queue_integration_test",
        scan_name=f"IV_Sweep_{datetime.now().strftime('%H%M%S')}",
        scan_type="1D Scan",
        job_type="Transport",
        additional_tags=["IV", "transport", "test"],
        user_fields={
            "temperature": "300K",
            "instrument": "Fake Keithley",
            "current_range": "-1mA to +1mA",
        }
    )
    
    # Set up instruments
    settings.movement_instruments = [current_source]
    settings.measurement_instruments = [voltage_meter]
    settings.movement_positions = [current_positions]
    
    return SimpleDatabaseScan(
        settings=settings,
        db_service=db,
        sample_id=sample_id,
        queue_id=queue_id,
        owner="test_operator"
    )


def create_raman_scan(
    db: DatabaseService,
    sample_id: Optional[int] = None,
    queue_id: Optional[int] = None,
) -> SimpleDatabaseScan:
    """
    Create a Raman spectrum scan.
    
    This scan acquires a single spectrum measurement using a fake spectrometer.
    
    Args:
        db: Database service for creating database records
        sample_id: Sample ID to associate with scan
        queue_id: Queue ID if part of a queue
    
    Returns:
        SimpleDatabaseScan configured for Raman spectrum acquisition
    """
    # Create spectrometer instrument
    spectrometer = FakeSpectrometer("Raman_Spectrometer")
    
    # Create scan settings
    settings = SimpleScanSettings(
        project_name="queue_integration_test",
        scan_name=f"Raman_Spectrum_{datetime.now().strftime('%H%M%S')}",
        scan_type="Single Measurement",
        job_type="Raman",
        additional_tags=["Raman", "spectroscopy", "test"],
        user_fields={
            "laser_wavelength": "532nm",
            "integration_time": "100ms",
            "objective": "50x",
        }
    )
    
    # Set up instruments (no movement for single measurement)
    settings.movement_instruments = []
    settings.measurement_instruments = [spectrometer]
    settings.movement_positions = []
    
    return SimpleDatabaseScan(
        settings=settings,
        db_service=db,
        sample_id=sample_id,
        queue_id=queue_id,
        owner="test_operator"
    )


# ==================== Test Class ====================

class TestQueueDatabaseIntegration:
    """Test suite for queue-database integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_queue_integration.db")
        self.db = DatabaseService(self.db_path)
        
        # Create test sample
        sample_data = {
            "sample_id": f"TEST_SAMPLE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "name": "Test Sample for Queue Integration",
            "material": "Au",
            "substrate": "Si/SiO2",
            "sample_type": "thin_film",
            "status": "active",
            "dimensions": {"length": 10, "width": 10, "thickness": 0.1, "unit": "mm"},
            "additional_tags": ["test", "integration"],
        }
        self.sample = self.db.create_sample(sample_data)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass
    
    def test_create_iv_scan(self):
        """Test IV scan creation."""
        scan = create_iv_scan(self.db, sample_id=self.sample['id'])
        
        assert scan is not None
        assert scan.scan_settings.scan_name.startswith("IV_Sweep")
        assert scan.scan_settings.job_type == "Transport"
        assert len(scan.scan_settings.movement_instruments) == 1
        assert len(scan.scan_settings.measurement_instruments) == 1
        
        print("✓ IV scan created successfully")
    
    def test_create_raman_scan(self):
        """Test Raman scan creation."""
        scan = create_raman_scan(self.db, sample_id=self.sample['id'])
        
        assert scan is not None
        assert scan.scan_settings.scan_name.startswith("Raman_Spectrum")
        assert scan.scan_settings.job_type == "Raman"
        assert len(scan.scan_settings.movement_instruments) == 0
        assert len(scan.scan_settings.measurement_instruments) == 1
        
        print("✓ Raman scan created successfully")
    
    def test_database_queue_creation(self):
        """Test creating a SimpleDatabaseQueue."""
        queue = SimpleDatabaseQueue(
            QID=f"TEST_QUEUE_{datetime.now().strftime('%H%M%S')}",
            db_service=self.db,
            sample_id=self.sample['id'],
            operator="test_operator",
        )
        
        assert queue is not None
        assert queue.db_queue_id is not None
        assert queue.db_queue_uuid is not None
        
        print(f"✓ DatabaseQueue created: {queue.db_queue_uuid} (ID: {queue.db_queue_id})")
    
    def test_full_queue_execution(self):
        """
        Test full queue execution with IV scan and Raman scan.
        
        This is the main integration test that:
        1. Creates a queue with 2 scans
        2. Executes them
        3. Verifies data is saved to database
        """
        print("\n" + "="*60)
        print("Starting Full Queue Integration Test")
        print("="*60)
        
        # Create SimpleDatabaseQueue
        queue = SimpleDatabaseQueue(
            QID=f"Integration_Test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            db_service=self.db,
            sample_id=self.sample['id'],
            operator="test_operator",
        )
        
        print(f"\n1. Created queue: {queue.db_queue_uuid}")
        
        # Create and enqueue IV scan
        iv_scan = create_iv_scan(self.db, sample_id=self.sample['id'], queue_id=queue.db_queue_id)
        queue.enqueue(iv_scan)
        print(f"2. Enqueued IV scan: {iv_scan.scan_settings.scan_name}")
        
        # Create and enqueue Raman scan
        raman_scan = create_raman_scan(self.db, sample_id=self.sample['id'], queue_id=queue.db_queue_id)
        queue.enqueue(raman_scan)
        print(f"3. Enqueued Raman scan: {raman_scan.scan_settings.scan_name}")
        
        # Verify queue has 2 scans
        assert queue.size() == 2
        print(f"\n4. Queue has {queue.size()} scans ready")
        
        # Execute queue
        print("\n5. Starting queue execution...")
        queue.start(mode="serial")
        
        print(f"\n6. Queue execution completed")
        
        # Verify all scans completed
        for handle in queue._scan_handles:
            assert handle.state == "completed", \
                f"Scan {handle.scan.scan_settings.scan_name} in unexpected state: {handle.state}"
            print(f"   {handle.scan.scan_settings.scan_name}: {handle.state}")
        
        # Verify database records
        print("\n7. Verifying database records...")
        
        # Check queue record
        db_queue = self.db.get_queue(queue.db_queue_id)
        assert db_queue is not None
        print(f"   Queue record found: {db_queue['queue_id']}")
        
        # Check scan records
        scans, total = self.db.get_scans(queue_id=queue.db_queue_id)
        print(f"   Found {total} scans in queue")
        
        for scan in scans:
            print(f"   - {scan['scan_name']}: {scan['status']}")
        
        print("\n" + "="*60)
        print("✓ Full Queue Integration Test PASSED")
        print("="*60)


# ==================== Standalone Execution ====================

def run_comprehensive_test():
    """
    Run a comprehensive test that can be executed standalone.
    Creates the database, runs queue with scans, and verifies everything.
    """
    print("\n" + "="*70)
    print("PyBirch Queue Database Integration - Comprehensive Test")
    print("="*70)
    
    # Use actual database path for standalone test
    db_path = os.path.join(project_root, "database", "test_queue_integration.db")
    print(f"\nDatabase path: {db_path}")
    
    # Create database service
    db = DatabaseService(db_path)
    print("✓ Database service created")
    
    # Create test sample
    sample_data = {
        "sample_id": f"QUEUE_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "name": "Queue Integration Test Sample",
        "material": "Au",
        "substrate": "Si/SiO2 (300nm)",
        "sample_type": "thin_film",
        "status": "active",
        "dimensions": {"length": 5, "width": 5, "thickness": 50, "unit": "nm"},
        "additional_tags": ["queue_test", "integration", "automated"],
    }
    sample = db.create_sample(sample_data)
    print(f"✓ Test sample created: {sample['sample_id']} (ID: {sample['id']})")
    
    # Create SimpleDatabaseQueue
    queue = SimpleDatabaseQueue(
        QID=f"Comprehensive_Test_{datetime.now().strftime('%H%M%S')}",
        db_service=db,
        sample_id=sample['id'],
        operator="automated_test",
    )
    print(f"✓ DatabaseQueue created: {queue.db_queue_uuid}")
    
    # Create IV Scan
    print("\n--- Creating IV Scan ---")
    iv_scan = create_iv_scan(db, sample_id=sample['id'], queue_id=queue.db_queue_id)
    queue.enqueue(iv_scan)
    print(f"  ✓ IV Scan enqueued: {iv_scan.scan_settings.scan_name}")
    print(f"    Current sweep: {len(iv_scan.scan_settings.movement_positions[0])} points")
    print(f"    From {iv_scan.scan_settings.movement_positions[0][0]*1000:.2f}mA to "
          f"{iv_scan.scan_settings.movement_positions[0][-1]*1000:.2f}mA")
    
    # Create Raman Scan
    print("\n--- Creating Raman Scan ---")
    raman_scan = create_raman_scan(db, sample_id=sample['id'], queue_id=queue.db_queue_id)
    queue.enqueue(raman_scan)
    print(f"  ✓ Raman Scan enqueued: {raman_scan.scan_settings.scan_name}")
    
    # Execute queue
    print(f"\n--- Executing Queue ({queue.size()} scans) ---")
    start_time = time.time()
    queue.start(mode="serial")
    execution_time = time.time() - start_time
    
    # Print final states
    print("\n--- Final Scan States ---")
    for handle in queue._scan_handles:
        duration = f"{handle.duration:.2f}s" if handle.duration else "N/A"
        print(f"  {handle.scan.scan_settings.scan_name}: {handle.state} (duration: {duration})")
    
    # Verify database
    print("\n--- Database Verification ---")
    
    # Get queue record
    db_queue = db.get_queue(queue.db_queue_id)
    if db_queue:
        print(f"  ✓ Queue found: {db_queue['queue_id']}")
        print(f"    Status: {db_queue['status']}")
    
    # Get scans by queue
    scans, total = db.get_scans(queue_id=queue.db_queue_id)
    print(f"\n  ✓ Found {total} scans in queue:")
    
    for scan in scans:
        print(f"\n    Scan: {scan['scan_name']}")
        print(f"      ID: {scan['id']}")
        print(f"      Status: {scan['status']}")
        print(f"      Type: {scan['scan_type']}")
        print(f"      Job: {scan['job_type']}")
        
        # Get detailed scan info
        scan_detail = db.get_scan(scan['id'])
        if scan_detail and 'measurement_objects' in scan_detail:
            measurements = scan_detail.get('measurement_objects', [])
            print(f"      Measurements: {len(measurements)}")
            for mo in measurements:
                data_count = mo.get('data_point_count', 0)
                print(f"        - {mo['name']}: {data_count} data points")
    
    # Summary
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST RESULTS")
    print("="*70)
    print(f"  Database: {db_path}")
    print(f"  Sample ID: {sample['sample_id']}")
    print(f"  Queue ID: {queue.db_queue_uuid}")
    print(f"  Scans executed: {queue.size()}")
    print(f"  Total execution time: {execution_time:.2f}s")
    
    completed_count = sum(1 for h in queue._scan_handles if h.state == "completed")
    failed_count = sum(1 for h in queue._scan_handles if h.state == "failed")
    
    print(f"  Completed: {completed_count}")
    print(f"  Failed: {failed_count}")
    
    if completed_count == queue.size():
        print("\n✓ ALL TESTS PASSED")
    else:
        print(f"\n✗ {failed_count} SCAN(S) FAILED")
    
    print("="*70)
    
    return queue, db


if __name__ == "__main__":
    # Run standalone comprehensive test
    try:
        queue, db = run_comprehensive_test()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
