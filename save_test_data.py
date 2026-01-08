"""
Save test queue and scans to the live database for UI testing.
"""
import os
import sys
import numpy as np
from datetime import datetime

os.environ['WANDB_MODE'] = 'disabled'

# Set up path to PyBirch root
PYBIRCH_ROOT = r'c:\Users\CJRGr\PyBirch'
sys.path.insert(0, PYBIRCH_ROOT)
os.chdir(PYBIRCH_ROOT)

from database.services import DatabaseService
from pybirch.setups.fake_setup.multimeter.multimeter import VoltageMeterMeasurement, CurrentSourceMovement
from pybirch.setups.fake_setup.spectrometer.spectrometer import FakeSpectrometer

# Use LIVE database with absolute path
DB_PATH = os.path.join(PYBIRCH_ROOT, 'database', 'pybirch.db')
db = DatabaseService(DB_PATH)
print(f'Using LIVE database: {DB_PATH}')

# Create or get test sample
sample = db.create_sample({
    'sample_id': f'UI_TEST_SAMPLE_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
    'name': 'UI Test Sample - Queue Integration',
    'material': 'Au',
    'substrate': 'Si/SiO2 (300nm)',
    'sample_type': 'thin_film',
    'status': 'active',
    'dimensions': {'length': 5, 'width': 5, 'thickness': 50, 'unit': 'nm'},
    'additional_tags': ['ui_test', 'queue_test'],
})
print(f'Created sample: {sample["sample_id"]} (ID: {sample["id"]})')

# Create queue
queue = db.create_queue({
    'name': 'UI Test Queue - IV + Raman',
    'sample_id': sample['id'],
    'status': 'completed',
    'execution_mode': 'serial',
    'created_by': 'test_operator',
    'total_scans': 2,
    'completed_scans': 2,
})
print(f'Created queue: {queue["queue_id"]} (ID: {queue["id"]})')

# Create IV Scan
iv_scan = db.create_scan({
    'scan_id': f'IV_Sweep_{datetime.now().strftime("%H%M%S")}',
    'project_name': 'ui_test_project',
    'scan_name': 'IV Sweep Test',
    'scan_type': '1D Scan',
    'job_type': 'Transport',
    'status': 'completed',
    'created_by': 'test_operator',
    'additional_tags': ['IV', 'transport', 'ui_test'],
    'sample_id': sample['id'],
    'queue_id': queue['id'],
    'extra_data': {'user_fields': {'temperature': '300K', 'instrument': 'Fake Keithley'}},
})
print(f'Created IV scan: {iv_scan["scan_id"]} (ID: {iv_scan["id"]})')

# Create IV measurement object and data
iv_mo = db.create_measurement_object(
    scan_id=iv_scan['id'],
    name='Voltage_Meter',
    columns=['current', 'voltage'],
    data_type='float',
    unit='V',
    instrument_name='IV_Voltage_Meter'
)

# Generate IV data
current_source = CurrentSourceMovement('Current_Source')
voltage_meter = VoltageMeterMeasurement('Voltage_Meter')
current_source.connect()
voltage_meter.connect()

iv_data_points = []
positions = np.linspace(-0.001, 0.001, 21)
for i, pos in enumerate(positions):
    current_source.position = pos
    data = voltage_meter.perform_measurement()
    for j, row in enumerate(data):
        iv_data_points.append({
            'values': {'current': float(pos), 'voltage': float(row[1])},
            'sequence_index': i * len(data) + j,
        })

db.bulk_create_data_points(iv_mo['id'], iv_data_points)
print(f'  Added {len(iv_data_points)} IV data points')

# Create Raman Scan
raman_scan = db.create_scan({
    'scan_id': f'Raman_Spectrum_{datetime.now().strftime("%H%M%S")}',
    'project_name': 'ui_test_project',
    'scan_name': 'Raman Spectrum Test',
    'scan_type': 'Single Measurement',
    'job_type': 'Raman',
    'status': 'completed',
    'created_by': 'test_operator',
    'additional_tags': ['Raman', 'spectroscopy', 'ui_test'],
    'sample_id': sample['id'],
    'queue_id': queue['id'],
    'extra_data': {'user_fields': {'laser': '532nm', 'power': '1mW', 'objective': '50x'}},
})
print(f'Created Raman scan: {raman_scan["scan_id"]} (ID: {raman_scan["id"]})')

# Create Raman measurement object and data
raman_mo = db.create_measurement_object(
    scan_id=raman_scan['id'],
    name='Spectrometer',
    columns=['wavelength', 'intensity'],
    data_type='float',
    unit='a.u.',
    instrument_name='Raman_Spectrometer'
)

# Generate Raman data
spectrometer = FakeSpectrometer('Spectrometer')
spectrometer.connect()
spectrum = spectrometer.perform_measurement()

raman_data_points = []
for i, row in enumerate(spectrum):
    raman_data_points.append({
        'values': {'wavelength': float(row[0]), 'intensity': float(row[1])},
        'sequence_index': i,
    })

db.bulk_create_data_points(raman_mo['id'], raman_data_points)
print(f'  Added {len(raman_data_points)} Raman data points')

print()
print('=' * 60)
print('TEST DATA SAVED TO LIVE DATABASE')
print('=' * 60)
print(f'Sample ID: {sample["id"]}')
print(f'Queue ID: {queue["id"]} ({queue["queue_id"]})')
print(f'IV Scan ID: {iv_scan["id"]}')
print(f'Raman Scan ID: {raman_scan["id"]}')
print()
print('View at:')
print(f'  Queue: http://127.0.0.1:5000/queues/{queue["id"]}')
print(f'  IV Scan: http://127.0.0.1:5000/scans/{iv_scan["id"]}')
print(f'  Raman Scan: http://127.0.0.1:5000/scans/{raman_scan["id"]}')
