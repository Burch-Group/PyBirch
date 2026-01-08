"""
Migration script to add failure_mode columns to procedures and fabrication_runs tables.

This migration adds:
- failure_modes (JSON) column to procedures table - stores list of possible failure modes
- failure_mode (VARCHAR) column to fabrication_runs table - stores selected failure mode when status is 'failed'

Run this script to update the database schema.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database.session import DatabaseManager
from sqlalchemy import text, inspect


def check_column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def migrate():
    """Add failure_mode columns to procedures and fabrication_runs tables."""
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    is_sqlite = db._is_sqlite
    
    print(f"Running migration on {'SQLite' if is_sqlite else 'PostgreSQL'} database...")
    
    with db.engine.connect() as conn:
        # Check and add failure_modes column to procedures table
        if not check_column_exists(inspector, 'procedures', 'failure_modes'):
            print("Adding 'failure_modes' column to procedures table...")
            conn.execute(text("""
                ALTER TABLE procedures
                ADD COLUMN failure_modes JSON NULL
            """))
            conn.commit()
            print("  ✓ Added 'failure_modes' column to procedures")
        else:
            print("  - 'failure_modes' column already exists in procedures")
        
        # Check and add failure_mode column to fabrication_runs table
        if not check_column_exists(inspector, 'fabrication_runs', 'failure_mode'):
            print("Adding 'failure_mode' column to fabrication_runs table...")
            conn.execute(text("""
                ALTER TABLE fabrication_runs
                ADD COLUMN failure_mode VARCHAR(255) NULL
            """))
            conn.commit()
            print("  ✓ Added 'failure_mode' column to fabrication_runs")
        else:
            print("  - 'failure_mode' column already exists in fabrication_runs")
    
    print("\n✅ Migration complete!")


def rollback():
    """Remove failure_mode columns (rollback migration)."""
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    is_sqlite = db._is_sqlite
    
    print(f"Running rollback on {'SQLite' if is_sqlite else 'PostgreSQL'} database...")
    
    with db.engine.connect() as conn:
        # Remove failure_modes column from procedures table
        if check_column_exists(inspector, 'procedures', 'failure_modes'):
            print("Removing 'failure_modes' column from procedures table...")
            conn.execute(text("""
                ALTER TABLE procedures
                DROP COLUMN failure_modes
            """))
            conn.commit()
            print("  ✓ Removed 'failure_modes' column from procedures")
        else:
            print("  - 'failure_modes' column does not exist in procedures")
        
        # Remove failure_mode column from fabrication_runs table
        if check_column_exists(inspector, 'fabrication_runs', 'failure_mode'):
            print("Removing 'failure_mode' column from fabrication_runs table...")
            conn.execute(text("""
                ALTER TABLE fabrication_runs
                DROP COLUMN failure_mode
            """))
            conn.commit()
            print("  ✓ Removed 'failure_mode' column from fabrication_runs")
        else:
            print("  - 'failure_mode' column does not exist in fabrication_runs")
    
    print("\n✅ Rollback complete!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Add failure_mode columns migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()
