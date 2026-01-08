"""
Script to add lab_id, project_id, and status columns to the templates table.

Works with both SQLite and PostgreSQL.
"""

from database.session import DatabaseManager
from sqlalchemy import text, inspect


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (database-agnostic)."""
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    db = DatabaseManager()
    inspector = inspect(db.engine)
    
    with db.session() as session:
        # Check existing columns using SQLAlchemy inspector (database-agnostic)
        columns = [col['name'] for col in inspector.get_columns('templates')]
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
