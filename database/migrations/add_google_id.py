"""
Migration script to add google_id column and make password_hash nullable for OAuth users.
Run this once to update existing databases for Google OAuth support.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.session import init_db

def migrate():
    """Add google_id column and fix password_hash for OAuth support."""
    db = init_db()
    
    with db.session() as session:
        # Check if google_id column exists
        try:
            session.execute(text("SELECT google_id FROM users LIMIT 1"))
            print("✓ google_id column already exists")
        except Exception:
            # Add the google_id column
            try:
                session.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(120)"))
                session.commit()
                print("✓ Added google_id column to users table")
            except Exception as e:
                print(f"Error adding google_id column: {e}")
                session.rollback()
        
        # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
        # to make password_hash nullable
        try:
            # Create new table with nullable password_hash
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255),
                    google_id VARCHAR(120) UNIQUE,
                    name VARCHAR(255),
                    role VARCHAR(50) DEFAULT 'user',
                    lab_id INTEGER REFERENCES labs(id),
                    is_active BOOLEAN DEFAULT 1,
                    last_login DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Copy data from old table
            session.execute(text("""
                INSERT INTO users_new (id, username, email, password_hash, google_id, name, role, lab_id, is_active, last_login, created_at, updated_at)
                SELECT id, username, email, password_hash, google_id, name, role, lab_id, is_active, last_login, created_at, updated_at
                FROM users
            """))
            
            # Drop old table and rename new one
            session.execute(text("DROP TABLE users"))
            session.execute(text("ALTER TABLE users_new RENAME TO users"))
            
            session.commit()
            print("✓ Updated password_hash column to allow NULL (for OAuth users)")
        except Exception as e:
            print(f"Error updating password_hash constraint: {e}")
            session.rollback()

if __name__ == "__main__":
    migrate()
