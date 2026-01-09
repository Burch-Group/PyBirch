"""
Migration: Add Archive Columns
==============================
Adds archived_at and archived_by columns to all archivable entities.

This migration adds the archive functionality that allows:
- Archived items are hidden from normal queries (unless show_archived filter is enabled)
- Archived items are preserved indefinitely (unlike trash which auto-deletes)

Run this migration by executing:
    python -m database.migrations.add_archive_columns
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import text
from database.session import get_session, init_db


# Tables that need archive columns
ARCHIVABLE_TABLES = [
    'templates',
    'labs',
    'projects',
    'issues',
    'instruments',
    'drivers',
    'driver_issues',
    'computers',
    'equipment',
    'equipment_issues',
    'precursors',
    'procedures',
    'samples',
    'fabrication_runs',
    'scan_templates',
    'queue_templates',
    'queues',
    'scans',
    'analyses',
    'entity_images',
    'attachments',
]


def column_exists(session, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (SQLite specific)."""
    result = session.execute(text(f"PRAGMA table_info({table_name})"))
    columns = [row[1] for row in result.fetchall()]
    return column_name in columns


def add_archive_columns():
    """Add archived_at and archived_by columns to all archivable tables."""
    init_db()
    
    with get_session() as session:
        for table_name in ARCHIVABLE_TABLES:
            # Check if table exists
            result = session.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            ))
            if not result.fetchone():
                print(f"  Table '{table_name}' does not exist, skipping...")
                continue
            
            # Add archived_at column if it doesn't exist
            if not column_exists(session, table_name, 'archived_at'):
                print(f"  Adding archived_at to {table_name}...")
                session.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN archived_at DATETIME"
                ))
            else:
                print(f"  Column archived_at already exists in {table_name}")
            
            # Add archived_by column if it doesn't exist
            if not column_exists(session, table_name, 'archived_by'):
                print(f"  Adding archived_by to {table_name}...")
                session.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN archived_by VARCHAR(100)"
                ))
            else:
                print(f"  Column archived_by already exists in {table_name}")
        
        session.commit()
        print("\n✅ Archive columns migration completed successfully!")


def create_archive_indexes():
    """Create indexes on archived_at columns for better query performance."""
    init_db()
    
    with get_session() as session:
        for table_name in ARCHIVABLE_TABLES:
            # Check if table exists
            result = session.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            ))
            if not result.fetchone():
                continue
            
            index_name = f"idx_{table_name}_archived_at"
            
            # Check if index already exists
            result = session.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'"
            ))
            if result.fetchone():
                print(f"  Index {index_name} already exists")
                continue
            
            # Create index
            if column_exists(session, table_name, 'archived_at'):
                print(f"  Creating index {index_name}...")
                session.execute(text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}(archived_at)"
                ))
        
        session.commit()
        print("\n✅ Archive indexes created successfully!")


if __name__ == '__main__':
    print("=" * 60)
    print("PyBirch Database Migration: Add Archive Columns")
    print("=" * 60)
    print("\nAdding archive columns to tables...")
    add_archive_columns()
    
    print("\nCreating indexes for archive columns...")
    create_archive_indexes()
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)
