"""
PyBirch Database Test Script
============================
Demonstrates and tests the database functionality.
Run this script to:
1. Initialize the database
2. Create sample data
3. Test CRUD operations
4. Verify relationships work correctly
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from database import (
    init_db, get_db, get_session, close_db,
    Sample, Scan, Queue, Template, Equipment, Precursor, Procedure,
    MeasurementObject, MeasurementDataPoint,
    sample_crud, scan_crud, queue_crud, template_crud,
    equipment_crud, precursor_crud, procedure_crud,
    generate_sample_id, generate_scan_id,
    add_tags_to_entity, get_entity_tags, search_samples,
    get_database_stats
)


def test_database():
    """Run comprehensive database tests."""
    print("=" * 60)
    print("PyBirch Database Test Suite")
    print("=" * 60)
    
    # Initialize database (creates tables)
    print("\n1. Initializing database...")
    db = init_db(echo=False)
    print(f"   Database URL: {db.database_url}")
    print(f"   Health check: {'PASSED' if db.health_check() else 'FAILED'}")
    
    # Test template creation
    print("\n2. Testing Templates...")
    with get_session() as session:
        # Create a sample template
        template = template_crud.create_template(
            session,
            name="Gold Thin Film",
            entity_type="sample",
            template_data={
                "material": "Au",
                "sample_type": "thin_film",
                "substrate": "Si/SiO2",
                "additional_tags": ["metal", "conductive"]
            },
            description="Template for gold thin film samples",
            created_by="test_script"
        )
        print(f"   Created template: {template}")
        template_id = template.id
    
    # Test equipment creation
    print("\n3. Testing Equipment...")
    with get_session() as session:
        equipment = equipment_crud.create(
            session,
            name="Keithley 2400",
            equipment_type="measurement",
            pybirch_class="Keithley2400",
            manufacturer="Keithley",
            model="2400",
            adapter="GPIB0::24::INSTR",
            status="available",
            specifications={"max_voltage": 200, "max_current": 1}
        )
        print(f"   Created equipment: {equipment}")
        equipment_id = equipment.id
    
    # Test precursor creation
    print("\n4. Testing Precursors...")
    with get_session() as session:
        precursor = precursor_crud.create(
            session,
            name="Gold Target",
            chemical_formula="Au",
            purity=99.99,
            state="solid",
            supplier="Kurt J. Lesker",
            storage_conditions="Room temperature, dry environment"
        )
        print(f"   Created precursor: {precursor}")
        
        # Add inventory
        inventory = precursor_crud.add_inventory(
            session,
            precursor_id=precursor.id,
            quantity=50.0,
            quantity_unit="g",
            location="Sputter Lab, Cabinet A"
        )
        print(f"   Added inventory: {inventory}")
        precursor_id = precursor.id
    
    # Test procedure creation
    print("\n5. Testing Procedures...")
    with get_session() as session:
        procedure = procedure_crud.create(
            session,
            name="Gold Sputtering",
            procedure_type="deposition",
            version="1.0",
            description="Standard gold sputtering procedure",
            steps=[
                {"step": 1, "action": "Load sample", "duration_min": 5},
                {"step": 2, "action": "Pump down to 1e-6 Torr", "duration_min": 30},
                {"step": 3, "action": "Sputter at 50W for 2 min", "duration_min": 2},
                {"step": 4, "action": "Cool down and vent", "duration_min": 15}
            ],
            parameters={
                "power_w": 50,
                "pressure_mtorr": 3,
                "ar_flow_sccm": 20,
                "duration_s": 120
            },
            estimated_duration_minutes=52,
            created_by="test_script"
        )
        print(f"   Created procedure: {procedure}")
        
        # Link equipment to procedure
        procedure_crud.add_equipment(
            session,
            procedure_id=procedure.id,
            equipment_id=equipment_id,
            role="source_meter"
        )
        print("   Linked equipment to procedure")
        
        # Link precursor to procedure
        procedure_crud.add_precursor(
            session,
            procedure_id=procedure.id,
            precursor_id=precursor_id,
            purpose="target material"
        )
        print("   Linked precursor to procedure")
        procedure_id = procedure.id
    
    # Test sample creation
    print("\n6. Testing Samples...")
    with get_session() as session:
        # Create sample from template
        sample = sample_crud.create_sample(
            session,
            sample_id="AU_TF_001",
            name="Gold Test Sample 1",
            template_id=template_id,
            substrate="Si/SiO2 (100)",
            dimensions={"length": 10, "width": 10, "thickness": 0.5, "unit": "mm"},
            created_by="test_script"
        )
        print(f"   Created sample: {sample}")
        
        # Add precursor to sample
        sample_crud.add_precursor(
            session,
            sample_id=sample.id,
            precursor_id=precursor_id,
            quantity_used=0.5,
            quantity_unit="g",
            role="primary",
            composition_percent=100.0
        )
        print("   Linked precursor to sample")
        sample_db_id = sample.id
    
    # Test scan creation
    print("\n7. Testing Scans...")
    with get_session() as session:
        scan = scan_crud.create_scan(
            session,
            project_name="test_project",
            scan_name="IV_Sweep_001",
            scan_type="1D Scan",
            job_type="Transport",
            owner="test_operator",
            sample_id=sample_db_id,
            status="running",
            started_at=datetime.utcnow(),
            additional_tags=["test", "IV"]
        )
        print(f"   Created scan: {scan}")
        
        # Add measurement object
        mobj = scan_crud.add_measurement_object(
            session,
            scan_id=scan.id,
            name="voltage_current",
            instrument_name="Keithley 2400",
            data_type="numeric",
            columns=["Voltage (V)", "Current (A)"]
        )
        print(f"   Created measurement object: {mobj}")
        
        # Add some test data
        test_data = [
            {"Voltage (V)": 0.0, "Current (A)": 0.0},
            {"Voltage (V)": 0.1, "Current (A)": 1e-6},
            {"Voltage (V)": 0.2, "Current (A)": 2e-6},
            {"Voltage (V)": 0.3, "Current (A)": 3e-6},
            {"Voltage (V)": 0.4, "Current (A)": 4e-6},
        ]
        
        count = scan_crud.add_measurement_data_batch(
            session,
            measurement_object_id=mobj.id,
            data_list=test_data,
            start_index=0
        )
        print(f"   Added {count} data points")
        
        # Update scan status
        scan_crud.update_status(
            session,
            scan.id,
            status="completed",
            completed_at=datetime.utcnow()
        )
        print("   Updated scan status to completed")
        scan_id = scan.id
    
    # Test queue creation
    print("\n8. Testing Queues...")
    with get_session() as session:
        queue = queue_crud.create_queue(
            session,
            name="Test Queue",
            sample_id=sample_db_id,
            execution_mode="SERIAL",
            operator="test_operator",
            total_scans=1
        )
        print(f"   Created queue: {queue}")
        
        # Link scan to queue
        scan = session.get(Scan, scan_id)
        scan.queue_id = queue.id
        scan.position_in_queue = 0
        print("   Linked scan to queue")
    
    # Test tagging
    print("\n9. Testing Tags...")
    with get_session() as session:
        sample = sample_crud.get_by_sample_id(session, "AU_TF_001")
        if sample:
            add_tags_to_entity("sample", sample.id, ["priority", "calibration"])
            tags = get_entity_tags("sample", sample.id)
            print(f"   Sample tags: {tags}")
    
    # Test search
    print("\n10. Testing Search...")
    results = search_samples(search_term="gold", limit=10)
    print(f"   Found {len(results)} samples matching 'gold'")
    for r in results:
        print(f"      - {r['sample_id']}: {r['material']} ({r['status']})")
    
    # Test statistics
    print("\n11. Database Statistics...")
    stats = get_database_stats()
    print(f"   Table counts:")
    for table, count in stats.items():
        if isinstance(count, int) and count >= 0:
            print(f"      - {table}: {count}")
    
    # Verify relationships
    print("\n12. Verifying Relationships...")
    with get_session() as session:
        sample = sample_crud.get_with_relations(session, sample_db_id)
        if sample:
            print(f"   Sample: {sample.sample_id}")
            print(f"   - Precursors: {len(sample.precursor_associations)}")
            print(f"   - Scans: {len(sample.scans)}")
            
            for scan in sample.scans:
                print(f"   - Scan '{scan.scan_name}': {scan.status}")
                print(f"     - Measurement objects: {len(scan.measurement_objects)}")
                for mobj in scan.measurement_objects:
                    print(f"       - {mobj.name}: {len(mobj.data_points)} data points")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
    
    # Print database location
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pybirch.db")
    print(f"\nDatabase file location: {db_path}")
    
    return True


def reset_database():
    """Reset the database (drop all tables and recreate)."""
    print("WARNING: This will delete all data in the database!")
    response = input("Are you sure? (yes/no): ")
    
    if response.lower() == "yes":
        db = get_db()
        db.drop_all()
        db.create_all()
        print("Database reset complete.")
    else:
        print("Operation cancelled.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PyBirch Database Test Script")
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    args = parser.parse_args()
    
    if args.reset:
        reset_database()
    else:
        test_database()
