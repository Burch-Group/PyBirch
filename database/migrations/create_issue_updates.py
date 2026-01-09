"""
Migration: Create issue_updates table for tracking issue update history.
"""

import sqlite3
import os

def migrate(db_path: str):
    """Create the issue_updates table."""
    print(f"Running migration on: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='issue_updates'")
        if cursor.fetchone():
            print("issue_updates table already exists")
            return
        
        # Create the table
        print("Creating issue_updates table...")
        cursor.execute("""
            CREATE TABLE issue_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_type VARCHAR(50) NOT NULL,
                issue_id INTEGER NOT NULL,
                update_type VARCHAR(50) DEFAULT 'comment',
                content TEXT,
                old_status VARCHAR(50),
                new_status VARCHAR(50),
                author_id INTEGER,
                author_name VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (author_id) REFERENCES users(id)
            )
        """)
        print("  - Table created")
        
        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX idx_issue_updates_issue ON issue_updates(issue_type, issue_id)")
        cursor.execute("CREATE INDEX idx_issue_updates_created ON issue_updates(created_at)")
        print("  - Indexes created")
        
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
