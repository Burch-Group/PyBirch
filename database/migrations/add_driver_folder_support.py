"""
Migration: Add folder upload support to drivers table.

Adds:
- driver_files: JSON list of files in the driver folder
- main_file_path: Path to the main instrument definition file
- has_folder_upload: Boolean flag for folder-based drivers

Run with: python -m database.migrations.add_driver_folder_support --db database/pybirch.db
"""

import sys
import os
from sqlalchemy import text, create_engine

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table."""
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        columns = [row[1] for row in result.fetchall()]
        return column_name in columns


def migrate(db_path):
    """Add folder upload support columns to drivers table."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    engine = create_engine(f'sqlite:///{db_path}')
    
    print("=" * 60)
    print("Adding Driver Folder Upload Support")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Add driver_files column
        if not check_column_exists(engine, 'drivers', 'driver_files'):
            print("\n1. Adding 'driver_files' column...")
            conn.execute(text("ALTER TABLE drivers ADD COLUMN driver_files TEXT"))
            conn.commit()
            print("   ✓ Column added")
        else:
            print("\n1. Column 'driver_files' already exists. Skipping.")
        
        # Add main_file_path column
        if not check_column_exists(engine, 'drivers', 'main_file_path'):
            print("\n2. Adding 'main_file_path' column...")
            conn.execute(text("ALTER TABLE drivers ADD COLUMN main_file_path VARCHAR(500)"))
            conn.commit()
            print("   ✓ Column added")
        else:
            print("\n2. Column 'main_file_path' already exists. Skipping.")
        
        # Add has_folder_upload column
        if not check_column_exists(engine, 'drivers', 'has_folder_upload'):
            print("\n3. Adding 'has_folder_upload' column...")
            conn.execute(text("ALTER TABLE drivers ADD COLUMN has_folder_upload BOOLEAN DEFAULT 0"))
            conn.commit()
            print("   ✓ Column added")
        else:
            print("\n3. Column 'has_folder_upload' already exists. Skipping.")
    
    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)
    return True


if __name__ == '__main__':
    db_path = None
    if '--db' in sys.argv:
        idx = sys.argv.index('--db')
        if idx + 1 < len(sys.argv):
            db_path = sys.argv[idx + 1]
    
    if not db_path:
        print("Usage: python -m database.migrations.add_driver_folder_support --db <database_path>")
        sys.exit(1)
    
    success = migrate(db_path)
    sys.exit(0 if success else 1)
