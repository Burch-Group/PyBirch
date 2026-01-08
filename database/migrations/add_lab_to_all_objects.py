"""
Migration: Add lab_id to all objects and user defaults
======================================================
Adds lab_id column to: precursors, procedures, queues, scans, 
scan_templates, queue_templates, fabrication_runs

Adds default_lab_id and default_project_id to users table

Works with both SQLite and PostgreSQL.

Run with: python -m database.migrations.add_lab_to_all_objects
"""

import os
import sys
from datetime import datetime

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
            # Tables to add lab_id to
            tables_needing_lab_id = [
                'precursors',
                'procedures',
                'queues',
                'scans',
                'scan_templates',
                'queue_templates',
                'fabrication_runs',
            ]
            
            for table in tables_needing_lab_id:
                if not table_exists(inspector, table):
                    print(f"Table {table} does not exist, skipping...")
                    continue
                    
                # Check if column already exists
                columns = [col['name'] for col in inspector.get_columns(table)]
                
                if 'lab_id' not in columns:
                    print(f"Adding lab_id to {table}...")
                    session.execute(text(f"ALTER TABLE {table} ADD COLUMN lab_id INTEGER"))
                    
                    # Try to set lab_id from associated project's lab_id
                    if 'project_id' in columns:
                        print(f"  Setting lab_id from project for {table}...")
                        session.execute(text(f"""
                            UPDATE {table} 
                            SET lab_id = (
                                SELECT lab_id FROM projects WHERE projects.id = {table}.project_id
                            )
                            WHERE project_id IS NOT NULL AND lab_id IS NULL
                        """))
                    
                    # Create index
                    print(f"  Creating index for {table}.lab_id...")
                    session.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_lab ON {table}(lab_id)"))
                else:
                    print(f"lab_id already exists in {table}, skipping...")
            
            # Add default_lab_id and default_project_id to users
            if table_exists(inspector, 'users'):
                user_columns = [col['name'] for col in inspector.get_columns('users')]
                
                if 'default_lab_id' not in user_columns:
                    print("Adding default_lab_id to users...")
                    session.execute(text("ALTER TABLE users ADD COLUMN default_lab_id INTEGER"))
                    # Initialize default_lab_id from user's lab_id
                    if 'lab_id' in user_columns:
                        session.execute(text("UPDATE users SET default_lab_id = lab_id WHERE lab_id IS NOT NULL"))
                else:
                    print("default_lab_id already exists in users, skipping...")
                
                if 'default_project_id' not in user_columns:
                    print("Adding default_project_id to users...")
                    session.execute(text("ALTER TABLE users ADD COLUMN default_project_id INTEGER"))
                else:
                    print("default_project_id already exists in users, skipping...")
            
            session.commit()
            print("\nMigration completed successfully!")
            
            # Print summary - refresh inspector to see new columns
            inspector = inspect(db.engine)
            print("\nSummary of changes:")
            for table in tables_needing_lab_id:
                if table_exists(inspector, table):
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE lab_id IS NOT NULL"))
                    count = result.scalar()
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    total = result.scalar()
                    print(f"  {table}: {count}/{total} rows have lab_id set")
            
            if table_exists(inspector, 'users'):
                result = session.execute(text("SELECT COUNT(*) FROM users WHERE default_lab_id IS NOT NULL"))
                users_with_default = result.scalar()
                result = session.execute(text("SELECT COUNT(*) FROM users"))
                total_users = result.scalar()
                print(f"  users: {users_with_default}/{total_users} have default_lab_id set")
            
        except Exception as e:
            session.rollback()
            print(f"Error during migration: {e}")
            raise


def migrate_down(db_path: str = None):
    """Revert the migration (remove added columns)."""
    if db_path:
        os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"
    
    db = DatabaseManager(create_tables=False)
    is_sqlite = db._is_sqlite
    
    print(f"Reverting migration for database: {db.database_url}")
    
    if is_sqlite:
        print("WARNING: SQLite doesn't support DROP COLUMN directly.")
        print("To fully revert, you would need to recreate tables without the columns.")
        print("For now, we'll just remove the indexes.")
    
    with db.session() as session:
        try:
            tables = [
                'precursors', 'procedures', 'queues', 'scans',
                'scan_templates', 'queue_templates', 'fabrication_runs'
            ]
            
            for table in tables:
                try:
                    session.execute(text(f"DROP INDEX IF EXISTS idx_{table}_lab"))
                    print(f"Dropped index idx_{table}_lab")
                except Exception as e:
                    print(f"Could not drop index for {table}: {e}")
            
            # For PostgreSQL, we can actually drop columns
            if not is_sqlite:
                print("\nDropping columns (PostgreSQL)...")
                for table in tables:
                    try:
                        session.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS lab_id"))
                        print(f"Dropped lab_id from {table}")
                    except Exception as e:
                        print(f"Could not drop column from {table}: {e}")
                
                try:
                    session.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS default_lab_id"))
                    session.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS default_project_id"))
                    print("Dropped default columns from users")
                except Exception as e:
                    print(f"Could not drop columns from users: {e}")
            
            session.commit()
            print("\nRevert completed.")
            if is_sqlite:
                print("Note: Columns remain in database but won't be used if model is reverted.")
            
        except Exception as e:
            session.rollback()
            print(f"Error during revert: {e}")
            raise


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        migrate_down()
    else:
        migrate_up()
