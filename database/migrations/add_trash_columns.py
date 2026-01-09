"""
Migration: Add soft-delete (trash) columns to all major entities.

This migration adds trashed_at and trashed_by columns to enable soft-delete functionality.
When an item is trashed:
- It is hidden from normal queries (unless show_trashed filter is enabled)
- It will be permanently deleted after 30 days
- For labs/projects, deletion cascades to all related objects
- For queues, trash propagates to scans
- For locations, trash propagates to child locations
"""

from sqlalchemy import text
from datetime import datetime


# Tables that need trash columns
TRASHABLE_TABLES = [
    'labs',
    'projects',
    'samples',
    'equipment',
    'precursors',
    'procedures',
    'instruments',
    'drivers',
    'computers',
    'queues',
    'scans',
    'locations',
    'templates',
    'scan_templates',
    'queue_templates',
    'fabrication_runs',
    'issues',
    'equipment_issues',
    'driver_issues',
    'analyses',
    'entity_images',
    'attachments',
]


def check_column_exists(conn, table_name, column_name):
    """Check if a column exists in a table (works for both SQLite and PostgreSQL)."""
    try:
        # Try PostgreSQL information_schema first
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = :table_name AND column_name = :column_name
        """), {"table_name": table_name, "column_name": column_name})
        return result.fetchone() is not None
    except:
        # Fallback to SQLite pragma
        try:
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]
            return column_name in columns
        except:
            return False


def check_index_exists(conn, index_name):
    """Check if an index exists (works for both SQLite and PostgreSQL)."""
    try:
        # PostgreSQL
        result = conn.execute(text("""
            SELECT indexname FROM pg_indexes WHERE indexname = :index_name
        """), {"index_name": index_name})
        return result.fetchone() is not None
    except:
        # SQLite
        try:
            result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='index' AND name=:index_name"),
                                  {"index_name": index_name})
            return result.fetchone() is not None
        except:
            return False


def migrate(engine):
    """Add trashed_at and trashed_by columns to all trashable tables."""
    with engine.begin() as conn:
        # Detect database type
        dialect = engine.dialect.name
        is_postgres = dialect == 'postgresql'
        
        for table in TRASHABLE_TABLES:
            print(f"Processing table: {table}")
            
            # Add trashed_at column if it doesn't exist
            if not check_column_exists(conn, table, 'trashed_at'):
                print(f"  Adding trashed_at column to {table}")
                if is_postgres:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN trashed_at TIMESTAMP NULL"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN trashed_at DATETIME NULL"))
            else:
                print(f"  trashed_at column already exists in {table}")
            
            # Add trashed_by column if it doesn't exist
            if not check_column_exists(conn, table, 'trashed_by'):
                print(f"  Adding trashed_by column to {table}")
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN trashed_by VARCHAR(100) NULL"))
            else:
                print(f"  trashed_by column already exists in {table}")
            
            # Add index on trashed_at for efficient filtering
            index_name = f"idx_{table}_trashed_at"
            if not check_index_exists(conn, index_name):
                print(f"  Creating index {index_name}")
                try:
                    conn.execute(text(f"CREATE INDEX {index_name} ON {table} (trashed_at)"))
                except Exception as e:
                    print(f"  Warning: Could not create index {index_name}: {e}")
            else:
                print(f"  Index {index_name} already exists")
        
        print("\nTrash columns migration completed successfully!")


def rollback(engine):
    """Remove trashed_at and trashed_by columns (for development/testing)."""
    with engine.begin() as conn:
        dialect = engine.dialect.name
        is_postgres = dialect == 'postgresql'
        
        for table in TRASHABLE_TABLES:
            print(f"Rolling back table: {table}")
            
            # Drop index first
            index_name = f"idx_{table}_trashed_at"
            if check_index_exists(conn, index_name):
                print(f"  Dropping index {index_name}")
                conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
            
            # Drop columns
            if is_postgres:
                if check_column_exists(conn, table, 'trashed_at'):
                    print(f"  Dropping trashed_at column from {table}")
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN trashed_at"))
                if check_column_exists(conn, table, 'trashed_by'):
                    print(f"  Dropping trashed_by column from {table}")
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN trashed_by"))
            else:
                # SQLite doesn't support DROP COLUMN easily
                print(f"  Warning: SQLite doesn't support DROP COLUMN. Manual table recreation needed for {table}")
        
        print("\nRollback completed!")


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from session import engine
    
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        rollback(engine)
    else:
        migrate(engine)
