"""
Migration: Add Location and ObjectLocation tables + Remove legacy location fields
==================================================================================
Creates the locations table for tracking physical locations in the lab
(rooms, cabinets, shelves, drawers, etc.) and the object_locations table
for tracking where objects are placed (with notes/directions).

Also removes legacy location fields from equipment, samples, and instruments,
and adds configurable type columns to labs.

Works with both SQLite and PostgreSQL.

Run with: python -m database.migrations.add_locations
"""

import os
import sys
from datetime import datetime

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text, inspect
from database.session import DatabaseManager


def table_exists(inspector, table_name: str) -> bool:
    """Check if a table exists (database-agnostic)."""
    return table_name in inspector.get_table_names()


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def migrate_up(db_path: str = None):
    """Apply the migration."""
    # If db_path provided, use it; otherwise use default/env
    if db_path:
        os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"
    
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    is_sqlite = db._is_sqlite
    
    print(f"Migrating database: {db.database_url}")
    print(f"Database type: {'SQLite' if is_sqlite else 'PostgreSQL'}")
    
    with db.session() as session:
        try:
            # Create locations table
            if not table_exists(inspector, 'locations'):
                print("Creating locations table...")
                session.execute(text("""
                    CREATE TABLE locations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lab_id INTEGER NOT NULL,
                        parent_location_id INTEGER,
                        name VARCHAR(255) NOT NULL,
                        location_type VARCHAR(50) DEFAULT 'other',
                        description TEXT,
                        room_number VARCHAR(50),
                        building VARCHAR(100),
                        floor VARCHAR(20),
                        capacity VARCHAR(100),
                        conditions TEXT,
                        access_notes TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        extra_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(255),
                        FOREIGN KEY (lab_id) REFERENCES labs(id),
                        FOREIGN KEY (parent_location_id) REFERENCES locations(id)
                    )
                """ if is_sqlite else """
                    CREATE TABLE locations (
                        id SERIAL PRIMARY KEY,
                        lab_id INTEGER NOT NULL REFERENCES labs(id),
                        parent_location_id INTEGER REFERENCES locations(id),
                        name VARCHAR(255) NOT NULL,
                        location_type VARCHAR(50) DEFAULT 'other',
                        description TEXT,
                        room_number VARCHAR(50),
                        building VARCHAR(100),
                        floor VARCHAR(20),
                        capacity VARCHAR(100),
                        conditions TEXT,
                        access_notes TEXT,
                        is_active BOOLEAN DEFAULT true,
                        extra_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by VARCHAR(255)
                    )
                """))
                
                # Create indexes for locations
                print("Creating indexes for locations table...")
                session.execute(text("CREATE INDEX idx_locations_lab_id ON locations(lab_id)"))
                session.execute(text("CREATE INDEX idx_locations_parent_id ON locations(parent_location_id)"))
                session.execute(text("CREATE INDEX idx_locations_type ON locations(location_type)"))
                print("Locations table created successfully.")
            else:
                print("Locations table already exists, skipping...")
            
            # Create object_locations table
            if not table_exists(inspector, 'object_locations'):
                print("Creating object_locations table...")
                session.execute(text("""
                    CREATE TABLE object_locations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        location_id INTEGER NOT NULL,
                        object_type VARCHAR(50) NOT NULL,
                        object_id INTEGER NOT NULL,
                        notes TEXT,
                        placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        placed_by VARCHAR(255),
                        is_current BOOLEAN DEFAULT 1,
                        FOREIGN KEY (location_id) REFERENCES locations(id)
                    )
                """ if is_sqlite else """
                    CREATE TABLE object_locations (
                        id SERIAL PRIMARY KEY,
                        location_id INTEGER NOT NULL REFERENCES locations(id),
                        object_type VARCHAR(50) NOT NULL,
                        object_id INTEGER NOT NULL,
                        notes TEXT,
                        placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        placed_by VARCHAR(255),
                        is_current BOOLEAN DEFAULT true
                    )
                """))
                
                # Create indexes for object_locations
                print("Creating indexes for object_locations table...")
                session.execute(text("CREATE INDEX idx_object_locations_location_id ON object_locations(location_id)"))
                session.execute(text("CREATE INDEX idx_object_locations_object ON object_locations(object_type, object_id)"))
                session.execute(text("CREATE INDEX idx_object_locations_current ON object_locations(is_current)"))
                print("Object_locations table created successfully.")
            else:
                print("Object_locations table already exists, skipping...")
            
            # Add configurable type columns to labs table
            if table_exists(inspector, 'labs'):
                if not column_exists(inspector, 'labs', 'location_types'):
                    print("Adding location_types column to labs...")
                    session.execute(text("ALTER TABLE labs ADD COLUMN location_types TEXT" if is_sqlite else "ALTER TABLE labs ADD COLUMN location_types JSONB"))
                    # Set default values for existing labs
                    default_location_types = '["room", "cabinet", "shelf", "drawer", "fridge", "freezer", "bench", "other"]'
                    session.execute(text(f"UPDATE labs SET location_types = '{default_location_types}'"))
                    print("  location_types column added with defaults.")
                
                if not column_exists(inspector, 'labs', 'equipment_types'):
                    print("Adding equipment_types column to labs...")
                    session.execute(text("ALTER TABLE labs ADD COLUMN equipment_types TEXT" if is_sqlite else "ALTER TABLE labs ADD COLUMN equipment_types JSONB"))
                    # Set default values for existing labs
                    default_equipment_types = '["glovebox", "chamber", "lithography", "furnace", "deposition", "etching", "characterization", "other"]'
                    session.execute(text(f"UPDATE labs SET equipment_types = '{default_equipment_types}'"))
                    print("  equipment_types column added with defaults.")
            
            # Remove legacy location columns (SQLite doesn't support DROP COLUMN directly)
            # For SQLite, we'll just leave the columns but they won't be used
            # For PostgreSQL, we can drop them
            if not is_sqlite:
                # Remove from equipment table
                if table_exists(inspector, 'equipment'):
                    if column_exists(inspector, 'equipment', 'location'):
                        print("Removing legacy 'location' column from equipment...")
                        session.execute(text("ALTER TABLE equipment DROP COLUMN location"))
                    if column_exists(inspector, 'equipment', 'room'):
                        print("Removing legacy 'room' column from equipment...")
                        session.execute(text("ALTER TABLE equipment DROP COLUMN room"))
                
                # Remove from samples table
                if table_exists(inspector, 'samples'):
                    if column_exists(inspector, 'samples', 'storage_location'):
                        print("Removing legacy 'storage_location' column from samples...")
                        session.execute(text("ALTER TABLE samples DROP COLUMN storage_location"))
                
                # Remove from instruments table
                if table_exists(inspector, 'instruments'):
                    if column_exists(inspector, 'instruments', 'location'):
                        print("Removing legacy 'location' column from instruments...")
                        session.execute(text("ALTER TABLE instruments DROP COLUMN location"))
            else:
                print("\nNote: SQLite doesn't support DROP COLUMN. Legacy columns remain but are unused.")
            
            session.commit()
            print("\nMigration completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"\nMigration failed: {e}")
            raise


def migrate_down(db_path: str = None):
    """Revert the migration."""
    if db_path:
        os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"
    
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    
    print(f"Rolling back migration on: {db.database_url}")
    
    with db.session() as session:
        try:
            # Drop tables in reverse order (due to foreign keys)
            if table_exists(inspector, 'object_locations'):
                print("Dropping object_locations table...")
                session.execute(text("DROP TABLE object_locations"))
            
            if table_exists(inspector, 'locations'):
                print("Dropping locations table...")
                session.execute(text("DROP TABLE locations"))
            
            session.commit()
            print("Rollback completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"Rollback failed: {e}")
            raise


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Location tables migration')
    parser.add_argument('--db', type=str, help='Path to SQLite database (optional)')
    parser.add_argument('--down', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    if args.down:
        migrate_down(args.db)
    else:
        migrate_up(args.db)
