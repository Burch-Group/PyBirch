"""
Migration: Add name, stored_filename, mime_type columns to attachments table.
Supports file upload functionality with name/description.
"""

import sqlite3
import os

def migrate(db_path: str):
    """Add new columns to attachments table."""
    print(f"Running migration on: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check which columns exist
        cursor.execute("PRAGMA table_info(attachments)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Add stored_filename column if it doesn't exist
        if 'stored_filename' not in existing_columns:
            print("Adding stored_filename column...")
            cursor.execute("ALTER TABLE attachments ADD COLUMN stored_filename VARCHAR(255)")
            # Copy file_path to stored_filename for existing records
            cursor.execute("UPDATE attachments SET stored_filename = file_path WHERE stored_filename IS NULL")
            print("  - Column added and populated from file_path")
        else:
            print("stored_filename column already exists")
        
        # Add name column if it doesn't exist
        if 'name' not in existing_columns:
            print("Adding name column...")
            cursor.execute("ALTER TABLE attachments ADD COLUMN name VARCHAR(255)")
            # Set name to filename for existing records
            cursor.execute("UPDATE attachments SET name = filename WHERE name IS NULL")
            print("  - Column added and populated from filename")
        else:
            print("name column already exists")
        
        # Add mime_type column if it doesn't exist
        if 'mime_type' not in existing_columns:
            print("Adding mime_type column...")
            cursor.execute("ALTER TABLE attachments ADD COLUMN mime_type VARCHAR(100)")
            print("  - Column added")
        else:
            print("mime_type column already exists")
        
        # Add index on created_at if it doesn't exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_attachments_created'")
        if not cursor.fetchone():
            print("Creating index idx_attachments_created...")
            cursor.execute("CREATE INDEX idx_attachments_created ON attachments(created_at)")
            print("  - Index created")
        else:
            print("Index idx_attachments_created already exists")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    # Default database path
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pybirch.db')
    
    if os.path.exists(db_path):
        migrate(db_path)
    else:
        print(f"Database not found at {db_path}")
        print("Run this migration after the database has been created.")
