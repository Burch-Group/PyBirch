"""
Migration: Add lab_id to computers table
========================================
Adds lab_id column to the computers table.

Works with both SQLite and PostgreSQL.

Run with: python -m database.migrations.add_computer_lab_id
"""

import os
import sys

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text, inspect
from database.session import DatabaseManager


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (database-agnostic)."""
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def table_exists(inspector, table_name: str) -> bool:
    """Check if a table exists (database-agnostic)."""
    return table_name in inspector.get_table_names()


def migrate_up(db_path: str = None):
    """Apply the migration."""
    # If db_path provided, use it; otherwise use default/env
    if db_path:
        os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"
    
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    is_sqlite = db._is_sqlite
    
    print(f"Migrating database: {db.database_url}")
    print(f"Database type: {'SQLite' if is_sqlite else 'PostgreSQL'}")
    
    with db.session() as session:
        try:
            # Check if computers table exists
            if not table_exists(inspector, 'computers'):
                print("  computers table does not exist, skipping migration")
                return
            
            # Add lab_id column to computers table
            if not column_exists(inspector, 'computers', 'lab_id'):
                print("  Adding lab_id column to computers table...")
                
                # Get the first lab id for default value
                result = session.execute(text("SELECT id FROM labs ORDER BY id LIMIT 1"))
                row = result.fetchone()
                default_lab_id = row[0] if row else 1
                
                if is_sqlite:
                    # SQLite: Add column without constraint first, then update
                    session.execute(text("""
                        ALTER TABLE computers 
                        ADD COLUMN lab_id INTEGER
                    """))
                    session.execute(text(f"""
                        UPDATE computers SET lab_id = {default_lab_id} WHERE lab_id IS NULL
                    """))
                else:
                    # PostgreSQL: Add column, set default, add constraint
                    session.execute(text("""
                        ALTER TABLE computers 
                        ADD COLUMN lab_id INTEGER
                    """))
                    session.execute(text(f"""
                        UPDATE computers SET lab_id = {default_lab_id} WHERE lab_id IS NULL
                    """))
                    session.execute(text("""
                        ALTER TABLE computers 
                        ALTER COLUMN lab_id SET NOT NULL
                    """))
                    session.execute(text("""
                        ALTER TABLE computers 
                        ADD CONSTRAINT fk_computers_lab_id 
                        FOREIGN KEY (lab_id) REFERENCES labs(id)
                    """))
                
                session.commit()
                print("  ✓ Added lab_id column to computers")
            else:
                print("  lab_id column already exists in computers table")
            
            # Add index on lab_id if it doesn't exist
            indexes = inspector.get_indexes('computers')
            index_names = [idx['name'] for idx in indexes]
            
            if 'idx_computer_lab' not in index_names:
                print("  Adding index on computers.lab_id...")
                session.execute(text("""
                    CREATE INDEX idx_computer_lab ON computers (lab_id)
                """))
                session.commit()
                print("  ✓ Added idx_computer_lab index")
            else:
                print("  idx_computer_lab index already exists")
            
            print("\nMigration completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"\nError during migration: {e}")
            raise


if __name__ == "__main__":
    migrate_up()
