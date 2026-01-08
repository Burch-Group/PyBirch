"""
Add Status Column to Instrument Definitions Migration
======================================================
Adds a status column to the instrument_definitions table.

Run with:
    python database/migrations/add_instrument_definition_status.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import create_engine, inspect, text


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate(db_path: str):
    """Run the migration to add status column to instrument_definitions."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Add status column
    if not check_column_exists(engine, 'instrument_definitions', 'status'):
        print("Adding status column to instrument_definitions...")
        
        alter_sql = """
        ALTER TABLE instrument_definitions ADD COLUMN status VARCHAR(50) DEFAULT 'operational'
        """
        
        with engine.connect() as conn:
            conn.execute(text(alter_sql))
            conn.commit()
        print("  ✓ status column added")
        
        # Create index
        print("Creating index...")
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX idx_instrument_def_status ON instrument_definitions(status)"))
            conn.commit()
        print("  ✓ Index created")
    else:
        print("status column already exists, skipping")
    
    print("\nMigration completed successfully!")
    return True


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='Add status column to instrument_definitions migration')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
