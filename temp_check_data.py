"""Check the test data structure in the database."""
import sys
sys.path.insert(0, 'c:\\Users\\CJRGr\\PyBirch')

from database.services import DatabaseService
db = DatabaseService('c:\\Users\\CJRGr\\PyBirch\\database\\pybirch.db')

# Get the test scan and its measurement objects
scan = db.get_scan(2)
print('=== IV Scan ===')
print(f'Scan ID: {scan["id"]}')
print(f'Measurement Objects: {len(scan["measurement_objects"])}')
for mo in scan['measurement_objects']:
    print(f'  - {mo["name"]}: columns={mo["columns"]}, unit={mo["unit"]}')

# Get a sample of data points
data = db.get_scan_data_points(2)
print(f'\nTotal data points: {len(data)}')
if data:
    print('\nFirst data point:')
    print(data[0])
    print('\nLast data point:')
    print(data[-1])

# Check Raman scan
print('\n=== Raman Scan ===')
scan3 = db.get_scan(3)
print(f'Scan ID: {scan3["id"]}')
print(f'Measurement Objects: {len(scan3["measurement_objects"])}')
for mo in scan3['measurement_objects']:
    print(f'  - {mo["name"]}: columns={mo["columns"]}, unit={mo["unit"]}')

data3 = db.get_scan_data_points(3)
print(f'\nTotal data points: {len(data3)}')
if data3:
    print('\nFirst data point:')
    print(data3[0])
