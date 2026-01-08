"""
Migration: Remove adapter and calibration columns from instruments table.

These columns are no longer needed:
- adapter: Connection info is now stored per-computer in computer_bindings table
- calibration_date: Calibration tracking was deemed unnecessary
- next_calibration_date: Calibration tracking was deemed unnecessary

Works with both SQLite and PostgreSQL.
"""

import os
import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text, inspect
from database.session import DatabaseManager


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (database-agnostic)."""
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def run_migration():
    """Run the migration."""
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    is_sqlite = db._is_sqlite
    
    print(f"Running migration on {'SQLite' if is_sqlite else 'PostgreSQL'} database...")
    
    columns_to_remove = ['adapter', 'calibration_date', 'next_calibration_date']
    
    with db.session() as session:
        try:
            for column in columns_to_remove:
                if column_exists(inspector, 'instruments', column):
                    print(f"  Dropping column: instruments.{column}")
                    
                    if is_sqlite:
                        # SQLite doesn't support DROP COLUMN directly in older versions
                        # For SQLite 3.35.0+ we can use ALTER TABLE DROP COLUMN
                        # We'll try the direct approach first
                        try:
                            session.execute(text(f"ALTER TABLE instruments DROP COLUMN {column}"))
                        except Exception as e:
                            print(f"    Note: SQLite may not support DROP COLUMN. Column will be ignored. ({e})")
                    else:
                        # PostgreSQL supports DROP COLUMN
                        session.execute(text(f"ALTER TABLE instruments DROP COLUMN IF EXISTS {column}"))
                else:
                    print(f"  Column instruments.{column} does not exist, skipping")
            
            session.commit()
            print("Migration completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"Migration failed: {e}")
            raise


if __name__ == '__main__':
    run_migration()
