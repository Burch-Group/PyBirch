"""
Script to add lab_id, project_id, and status columns to the templates table.
"""

from database.session import DatabaseManager
from sqlalchemy import text

def migrate():
    db = DatabaseManager()
    
    with db.session() as session:
        # Check existing columns
        result = session.execute(text("PRAGMA table_info(templates)"))
        columns = [row[1] for row in result.fetchall()]
        print(f"Existing columns: {columns}")
        
        # Add lab_id if not exists
        if 'lab_id' not in columns:
            session.execute(text('ALTER TABLE templates ADD COLUMN lab_id INTEGER'))
            print("Added lab_id column")
        else:
            print("lab_id column already exists")
        
        # Add project_id if not exists
        if 'project_id' not in columns:
            session.execute(text('ALTER TABLE templates ADD COLUMN project_id INTEGER'))
            print("Added project_id column")
        else:
            print("project_id column already exists")
        
        # Add status if not exists
        if 'status' not in columns:
            session.execute(text("ALTER TABLE templates ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
            print("Added status column")
        else:
            print("status column already exists")
        
        session.commit()
        print("Migration complete!")

if __name__ == "__main__":
    migrate()
