"""
Add scroll_pixels Column to Page Views Migration
================================================
Adds scroll_pixels column to page_views table for tracking scroll distance.

Run with:
    python database/migrations/add_scroll_pixels.py --db database/pybirch.db
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
    """Run the migration to add scroll_pixels column to page_views."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Check if page_views table exists
    inspector = inspect(engine)
    if 'page_views' not in inspector.get_table_names():
        print("page_views table does not exist, skipping...")
        return True
    
    # Add scroll_pixels column if it doesn't exist
    if not check_column_exists(engine, 'page_views', 'scroll_pixels'):
        print("Adding scroll_pixels column to page_views table...")
        
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE page_views ADD COLUMN scroll_pixels INTEGER"))
            conn.commit()
        print("  ✓ scroll_pixels column added")
    else:
        print("scroll_pixels column already exists, skipping...")
    
    print("\nMigration complete!")
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Add scroll_pixels column migration')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)
