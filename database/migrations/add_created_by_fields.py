"""
Add created_by Fields Migration
===============================
Adds created_by column to equipment, instruments, and precursors tables.

Run with:
    python database/migrations/add_created_by_fields.py --db database/pybirch.db
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
    """Run the migration to add created_by fields."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    tables_to_update = ['equipment', 'instruments', 'precursors']
    
    for table_name in tables_to_update:
        if not check_column_exists(engine, table_name, 'created_by'):
            print(f"Adding created_by column to {table_name} table...")
            
            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN created_by VARCHAR(100)"
            
            with engine.connect() as conn:
                conn.execute(text(alter_sql))
                conn.commit()
            print(f"  ✓ created_by column added to {table_name}")
        else:
            print(f"{table_name} table already has created_by column, skipping...")
    
    print("\n✅ Migration complete!")
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Add created_by fields to equipment, instruments, and precursors')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)
