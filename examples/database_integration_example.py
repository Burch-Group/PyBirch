"""
PyBirch Database Integration Example
====================================
This example demonstrates how to use the database integration with PyBirch scans.

The integration layer automatically:
- Creates database records when scans start
- Persists measurement data during scans
- Updates scan status in real-time
- Handles errors and aborts gracefully
"""

from datetime import datetime
import numpy as np
import pandas as pd

# Database imports
from database.services import DatabaseService

# PyBirch imports (these would be your actual imports)
# from pybirch.scan import Scan, ScanSettings
# from pybirch.queue import Queue

# Database integration imports
from pybirch.database_integration import (
    DatabaseExtension,
    DatabaseQueueExtension,
    ScanManager,
    QueueManager,
    EquipmentManager,
    DataManager,
)


def example_basic_scan_integration():
    """
    Basic example: Using DatabaseExtension with a single scan.
    """
    print("=" * 60)
    print("Example 1: Basic Scan Integration")
    print("=" * 60)
    
    # Initialize database service
    db = DatabaseService('example_database.db')
    
    # First, create or get a sample to associate with the scan
    sample = db.create_sample({
        'name': 'Test Sample A',
        'material': 'Silicon',
        'description': 'Test sample for integration demo',
    })
    print(f"Created sample: {sample['name']} (ID: {sample['id']})")
    
    # Create the database extension
    # This will automatically track the scan in the database
    db_extension = DatabaseExtension(
        db_service=db,
        sample_id=sample['id'],
        buffer_size=50,  # Flush every 50 data points
        owner='Demo User',
    )
    
    # Simulate a PyBirch scan workflow
    
    # 1. Scan startup - creates database record
    class MockScan:
        """Mock scan for demonstration."""
        def __init__(self):
            self.scan_settings = MockScanSettings()
            self.owner = 'Demo User'
    
    class MockScanSettings:
        """Mock scan settings."""
        scan_type = 'line_scan'
        num_scans = 1
        scan_rate = 10.0
        dwell_time = 0.1
        measurement_items = []
        movement_items = []
        metadata = {'purpose': 'demo'}
    
    scan = MockScan()
    db_extension.startup(scan)
    
    # 2. Scan execution begins
    db_extension.execute()
    
    # 3. During scan, data is collected and saved
    # Simulate measurement data
    for i in range(10):
        df = pd.DataFrame({
            'x': [i * 0.1],
            'y': [np.sin(i * 0.1)],
            'z': [np.cos(i * 0.1)],
        })
        db_extension.save_data(df, 'position_measurement')
    
    # 4. Scan completes
    db_extension.on_complete(wandb_link='https://wandb.ai/example/run/123')
    
    # Verify the scan was saved
    scan_info = db_extension.get_scan_info()
    print(f"Scan completed: {scan_info['scan_id']}")
    print(f"Status: {scan_info['status']}")
    print(f"W&B Link: {scan_info.get('wandb_link')}")
    
    print()


def example_queue_integration():
    """
    Example: Using DatabaseQueueExtension with a queue of scans.
    """
    print("=" * 60)
    print("Example 2: Queue Integration")
    print("=" * 60)
    
    db = DatabaseService('example_database.db')
    
    # Create sample for the queue
    sample = db.create_sample({
        'name': 'Test Sample B',
        'material': 'GaAs',
        'description': 'Sample for queue demo',
    })
    
    # Create queue extension
    queue_ext = DatabaseQueueExtension(
        db_service=db,
        operator='Demo Operator',
    )
    
    # Mock PyBirch queue
    class MockQueue:
        queue_id = 'Q-DEMO-001'
        name = 'Demo Queue'
        total_scans = 3
        execution_mode = 'sequential'
    
    pybirch_queue = MockQueue()
    
    # 1. Queue is created
    queue_ext.on_queue_create(pybirch_queue, sample_id=sample['id'])
    
    # 2. Queue starts
    queue_ext.on_queue_start()
    queue_ext.log('INFO', 'Queue execution started')
    
    # 3. Run scans in the queue
    for i in range(3):
        # Create scan extension linked to this queue
        scan_ext = queue_ext.create_scan_extension(sample_id=sample['id'])
        
        # Simulate scan workflow
        class MockScanInQueue:
            scan_settings = type('Settings', (), {
                'scan_type': f'scan_{i}',
                'num_scans': 1,
                'scan_rate': 5.0,
                'dwell_time': 0.05,
                'measurement_items': [],
                'movement_items': [],
                'metadata': {'queue_index': i},
            })()
            owner = 'Demo Operator'
        
        scan = MockScanInQueue()
        scan_ext.startup(scan)
        scan_ext.execute()
        
        # Simulate some data
        df = pd.DataFrame({'value': [i * 10 + j for j in range(5)]})
        scan_ext.save_data(df, 'detector')
        
        scan_ext.on_complete()
        queue_ext.on_scan_complete()
        queue_ext.log('INFO', f'Scan {i+1}/3 completed')
    
    # 4. Queue completes
    queue_ext.on_queue_complete()
    
    print(f"Queue completed: {queue_ext._queue_id}")
    print()


def example_equipment_management():
    """
    Example: Using EquipmentManager to track instruments.
    """
    print("=" * 60)
    print("Example 3: Equipment Management")
    print("=" * 60)
    
    db = DatabaseService('example_database.db')
    equipment_mgr = EquipmentManager(db)
    
    # Mock PyBirch instrument
    class MockInstrument:
        name = 'Keithley_2400'
        manufacturer = 'Keithley'
        model = '2400'
        serial_number = 'SN12345'
        visa_address = 'GPIB0::24::INSTR'
        settings = {
            'compliance_voltage': 10.0,
            'measurement_range': 'auto',
            'nplc': 1.0,
        }
    
    instrument = MockInstrument()
    
    # Register the instrument
    equipment = equipment_mgr.register_instrument(instrument)
    print(f"Registered: {equipment['name']} (ID: {equipment['id']})")
    
    # Update status
    equipment_mgr.update_status(instrument.name, 'active', 'Measuring IV curve')
    print(f"Status updated to: active")
    
    # Save settings
    equipment_mgr.save_settings(instrument.name, instrument.settings)
    print(f"Settings saved")
    
    # Load settings back
    settings = equipment_mgr.get_settings(instrument.name)
    print(f"Loaded settings: {settings}")
    
    print()


def example_data_manager():
    """
    Example: Using DataManager directly for data persistence.
    """
    print("=" * 60)
    print("Example 4: Data Management")
    print("=" * 60)
    
    db = DatabaseService('example_database.db')
    data_mgr = DataManager(db, buffer_size=10)
    
    # First create a scan to associate data with
    scan = db.create_scan({
        'scan_name': 'Data Manager Demo',
        'scan_type': 'test',
        'owner': 'Demo',
    })
    scan_id = scan['id']
    
    # Create a measurement object
    mo = data_mgr.create_measurement_object(
        scan_id=scan_id,
        name='temperature',
        data_type='float',
        unit='K',
        instrument_name='Lakeshore_336',
        description='Sample temperature during measurement',
    )
    print(f"Created measurement object: {mo['name']} (ID: {mo['id']})")
    
    # Save individual data points (buffered)
    for i in range(25):
        data_mgr.save_data_point(
            scan_id=scan_id,
            measurement_name='temperature',
            values={'temperature': 300.0 + i * 0.5},
            sequence_index=i,
        )
    
    # Manual flush to ensure all data is written
    data_mgr.flush(scan_id)
    
    # Retrieve the data
    df = data_mgr.get_data(scan_id, 'temperature')
    print(f"Retrieved {len(df)} data points")
    print(df.head())
    
    # Save array data (e.g., spectrum)
    spectrum = np.random.random(1000)
    data_mgr.save_array(
        scan_id=scan_id,
        measurement_name='spectrum',
        data=spectrum,
        extra_data={'wavelength_start': 400, 'wavelength_end': 800},
    )
    print(f"Saved spectrum array ({len(spectrum)} points)")
    
    print()


def example_error_handling():
    """
    Example: How errors are handled during scans.
    """
    print("=" * 60)
    print("Example 5: Error Handling")
    print("=" * 60)
    
    db = DatabaseService('example_database.db')
    
    db_extension = DatabaseExtension(
        db_service=db,
        owner='Demo User',
    )
    
    class MockScan:
        scan_settings = type('Settings', (), {
            'scan_type': 'error_demo',
            'num_scans': 1,
            'scan_rate': 1.0,
            'dwell_time': 0.1,
            'measurement_items': [],
            'movement_items': [],
            'metadata': {},
        })()
        owner = 'Demo User'
    
    scan = MockScan()
    db_extension.startup(scan)
    db_extension.execute()
    
    # Simulate some data before error
    df = pd.DataFrame({'value': [1, 2, 3]})
    db_extension.save_data(df, 'measurement')
    
    # Simulate an error
    try:
        raise RuntimeError("Instrument communication timeout")
    except Exception as e:
        db_extension.on_error(e)
    
    # Check the status
    scan_info = db_extension.get_scan_info()
    print(f"Scan {scan_info['scan_id']}: {scan_info['status']}")
    
    print()


if __name__ == '__main__':
    # Run all examples
    # Note: These require the database to be properly set up
    
    print("PyBirch Database Integration Examples")
    print("=" * 60)
    print()
    print("NOTE: These examples use mock objects to demonstrate")
    print("the integration pattern. In real usage, you would use")
    print("actual PyBirch Scan and Queue objects.")
    print()
    
    try:
        example_basic_scan_integration()
        example_queue_integration()
        example_equipment_management()
        example_data_manager()
        example_error_handling()
    except Exception as e:
        print(f"Error running examples: {e}")
        print("Make sure the database is properly configured.")
    
    print("=" * 60)
    print("Examples completed!")
