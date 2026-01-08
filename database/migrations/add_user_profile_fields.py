"""
Migration script to add phone, orcid, and office_location columns to users table.
These fields allow users to manage their personal info from their profile page.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.session import init_db

def migrate():
    """Add phone, orcid, and office_location columns to users table."""
    db = init_db()
    
    with db.session() as session:
        # Check and add phone column
        try:
            session.execute(text("SELECT phone FROM users LIMIT 1"))
            print("✓ phone column already exists")
        except Exception:
            try:
                session.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(50)"))
                session.commit()
                print("✓ Added phone column to users table")
            except Exception as e:
                print(f"Error adding phone column: {e}")
                session.rollback()
        
        # Check and add orcid column
        try:
            session.execute(text("SELECT orcid FROM users LIMIT 1"))
            print("✓ orcid column already exists")
        except Exception:
            try:
                session.execute(text("ALTER TABLE users ADD COLUMN orcid VARCHAR(50)"))
                session.commit()
                print("✓ Added orcid column to users table")
            except Exception as e:
                print(f"Error adding orcid column: {e}")
                session.rollback()
        
        # Check and add office_location column
        try:
            session.execute(text("SELECT office_location FROM users LIMIT 1"))
            print("✓ office_location column already exists")
        except Exception:
            try:
                session.execute(text("ALTER TABLE users ADD COLUMN office_location VARCHAR(255)"))
                session.commit()
                print("✓ Added office_location column to users table")
            except Exception as e:
                print(f"Error adding office_location column: {e}")
                session.rollback()

    print("\nMigration complete!")

if __name__ == "__main__":
    migrate()
