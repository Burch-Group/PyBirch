"""Test script for InstrumentFactory database loading."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.services import DatabaseService
from pybirch.Instruments.factory import InstrumentFactory

def main():
    print("Testing InstrumentFactory database loading...")
    
    # Connect to database
    db = DatabaseService('database/pybirch.db')
    factory = InstrumentFactory(db)
    
    # Get definitions
    defs = factory.get_available_definitions()
    print(f"Found {len(defs)} definitions in database")
    
    for defn in defs:
        print(f"  - {defn['name']} ({defn['instrument_type']})")
    
    # Try to create classes
    print("\nCreating classes from definitions...")
    for defn in defs:
        try:
            cls = factory.create_class_from_definition(defn)
            print(f"  ✓ {defn['name']} -> {cls}")
        except Exception as e:
            print(f"  ✗ {defn['name']} - Error: {e}")
    
    # Test instantiation with FakeLockInAmplifier (no external dependencies)
    print("\nTesting instantiation...")
    lock_in_def = next((d for d in defs if d['name'] == 'FakeLockInAmplifier'), None)
    if lock_in_def:
        try:
            instance = factory.create_instance(lock_in_def)
            print(f"  ✓ Created instance: {instance}")
            print(f"    - Name: {instance.name}")
            if hasattr(instance, 'data_columns'):
                print(f"    - Data columns: {instance.data_columns}")
            if hasattr(instance, 'settings'):
                print(f"    - Settings: {instance.settings}")
        except Exception as e:
            print(f"  ✗ Error creating instance: {e}")
            import traceback
            traceback.print_exc()
    
    # Test FakeXStage
    stage_def = next((d for d in defs if d['name'] == 'FakeXStage'), None)
    if stage_def:
        try:
            instance = factory.create_instance(stage_def)
            print(f"  ✓ Created FakeXStage: {instance}")
            print(f"    - Position units: {instance.position_units}")
        except Exception as e:
            print(f"  ✗ FakeXStage error: {e}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
