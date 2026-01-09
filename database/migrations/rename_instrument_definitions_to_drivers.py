"""
Rename Instrument Definitions to Drivers Migration
===================================================
Renames tables and columns from 'instrument_definition(s)' to 'driver(s)':
- instrument_definitions → drivers
- instrument_definition_versions → driver_versions
- instrument_definition_issues → driver_issues
- definition_id → driver_id (in all related tables)

Run with:
    python database/migrations/rename_instrument_definitions_to_drivers.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import create_engine, inspect, text


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate(db_path: str):
    """Run the migration to rename instrument_definitions to drivers."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    print("=" * 60)
    print("Renaming Instrument Definitions to Drivers")
    print("=" * 60)
    
    # 1. Rename instrument_definitions table to drivers
    if check_table_exists(engine, 'instrument_definitions') and not check_table_exists(engine, 'drivers'):
        print("\n1. Renaming 'instrument_definitions' table to 'drivers'...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE instrument_definitions RENAME TO drivers"))
            conn.commit()
        print("   ✓ Table renamed")
    elif check_table_exists(engine, 'drivers'):
        print("\n1. Table 'drivers' already exists. Skipping rename.")
    else:
        print("\n1. Table 'instrument_definitions' does not exist. Skipping.")
    
    # 2. Rename instrument_definition_versions table to driver_versions
    if check_table_exists(engine, 'instrument_definition_versions') and not check_table_exists(engine, 'driver_versions'):
        print("\n2. Renaming 'instrument_definition_versions' table to 'driver_versions'...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE instrument_definition_versions RENAME TO driver_versions"))
            conn.commit()
        print("   ✓ Table renamed")
    elif check_table_exists(engine, 'driver_versions'):
        print("\n2. Table 'driver_versions' already exists. Skipping rename.")
    else:
        print("\n2. Table 'instrument_definition_versions' does not exist. Skipping.")
    
    # 3. Rename instrument_definition_issues table to driver_issues
    if check_table_exists(engine, 'instrument_definition_issues') and not check_table_exists(engine, 'driver_issues'):
        print("\n3. Renaming 'instrument_definition_issues' table to 'driver_issues'...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE instrument_definition_issues RENAME TO driver_issues"))
            conn.commit()
        print("   ✓ Table renamed")
    elif check_table_exists(engine, 'driver_issues'):
        print("\n3. Table 'driver_issues' already exists. Skipping rename.")
    else:
        print("\n3. Table 'instrument_definition_issues' does not exist. Skipping.")
    
    # 4. Rename definition_id column in instruments table to driver_id
    if check_table_exists(engine, 'instruments'):
        if check_column_exists(engine, 'instruments', 'definition_id') and not check_column_exists(engine, 'instruments', 'driver_id'):
            print("\n4. Renaming 'definition_id' to 'driver_id' in 'instruments' table...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE instruments RENAME COLUMN definition_id TO driver_id"))
                conn.commit()
            print("   ✓ Column renamed")
        elif check_column_exists(engine, 'instruments', 'driver_id'):
            print("\n4. Column 'driver_id' already exists in 'instruments'. Skipping.")
        else:
            print("\n4. Column 'definition_id' does not exist in 'instruments'. Skipping.")
    else:
        print("\n4. Table 'instruments' does not exist. Skipping.")
    
    # 5. Rename definition_id column in driver_versions table to driver_id
    versions_table = 'driver_versions' if check_table_exists(engine, 'driver_versions') else 'instrument_definition_versions'
    if check_table_exists(engine, versions_table):
        if check_column_exists(engine, versions_table, 'definition_id') and not check_column_exists(engine, versions_table, 'driver_id'):
            print(f"\n5. Renaming 'definition_id' to 'driver_id' in '{versions_table}' table...")
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {versions_table} RENAME COLUMN definition_id TO driver_id"))
                conn.commit()
            print("   ✓ Column renamed")
        elif check_column_exists(engine, versions_table, 'driver_id'):
            print(f"\n5. Column 'driver_id' already exists in '{versions_table}'. Skipping.")
        else:
            print(f"\n5. Column 'definition_id' does not exist in '{versions_table}'. Skipping.")
    else:
        print("\n5. Versions table does not exist. Skipping.")
    
    # 6. Rename definition_id column in driver_issues table to driver_id
    issues_table = 'driver_issues' if check_table_exists(engine, 'driver_issues') else 'instrument_definition_issues'
    if check_table_exists(engine, issues_table):
        if check_column_exists(engine, issues_table, 'definition_id') and not check_column_exists(engine, issues_table, 'driver_id'):
            print(f"\n6. Renaming 'definition_id' to 'driver_id' in '{issues_table}' table...")
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {issues_table} RENAME COLUMN definition_id TO driver_id"))
                conn.commit()
            print("   ✓ Column renamed")
        elif check_column_exists(engine, issues_table, 'driver_id'):
            print(f"\n6. Column 'driver_id' already exists in '{issues_table}'. Skipping.")
        else:
            print(f"\n6. Column 'definition_id' does not exist in '{issues_table}'. Skipping.")
    else:
        print("\n6. Issues table does not exist. Skipping.")
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
    
    return True


if __name__ == '__main__':
    # Parse command line arguments
    db_path = None
    if '--db' in sys.argv:
        idx = sys.argv.index('--db')
        if idx + 1 < len(sys.argv):
            db_path = sys.argv[idx + 1]
    
    if not db_path:
        print("Usage: python rename_instrument_definitions_to_drivers.py --db <database_path>")
        sys.exit(1)
    
    success = migrate(db_path)
    sys.exit(0 if success else 1)
