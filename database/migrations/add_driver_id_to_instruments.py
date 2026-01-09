"""
Migration: Add driver_id column to instruments table.
This links instruments to their driver definitions.
"""

from sqlalchemy import text


def check_column_exists(conn, table_name, column_name):
    """Check if a column exists in a table."""
    try:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        columns = [row[1] for row in result.fetchall()]
        return column_name in columns
    except:
        return False


def migrate(engine):
    """Add driver_id column to instruments table."""
    with engine.begin() as conn:
        print("Processing instruments table...")
        
        # Add driver_id column if it doesn't exist
        if not check_column_exists(conn, 'instruments', 'driver_id'):
            print("  Adding driver_id column to instruments")
            conn.execute(text("ALTER TABLE instruments ADD COLUMN driver_id INTEGER REFERENCES drivers(id)"))
            print("  driver_id column added successfully")
        else:
            print("  driver_id column already exists")
        
        print("\nMigration completed!")


if __name__ == '__main__':
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    from database.session import init_db
    db = init_db()
    migrate(db.engine)
