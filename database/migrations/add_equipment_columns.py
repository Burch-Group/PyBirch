"""
Migration: Add new columns to equipment table for enhanced equipment management.

This migration adds:
- description (text)
- room (string)
- owner_id (foreign key to users)
- purchase_date (date)
- warranty_expiration (date)
- last_maintenance_date (date)
- next_maintenance_date (date)
- maintenance_interval_days (integer)
- specifications (JSON)
- documentation_url (string)

Also creates new tables:
- equipment_images
- equipment_issues
- procedure_equipment

Works with both SQLite and PostgreSQL.
"""

import os
import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text, inspect
from database.session import DatabaseManager


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (database-agnostic)."""
    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def table_exists(inspector, table_name: str) -> bool:
    """Check if a table exists (database-agnostic)."""
    return table_name in inspector.get_table_names()


def run_migration():
    """Run the migration."""
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    is_sqlite = db._is_sqlite
    
    print(f"Running migration on {'SQLite' if is_sqlite else 'PostgreSQL'} database...")
    
    with db.session() as session:
        try:
            # Add new columns to equipment table
            new_columns = [
                ("description", "TEXT"),
                ("room", "VARCHAR(100)"),
                ("owner_id", "INTEGER"),  # REFERENCES handled by ORM
                ("purchase_date", "DATE"),
                ("warranty_expiration", "DATE"),
                ("last_maintenance_date", "DATE"),
                ("next_maintenance_date", "DATE"),
                ("maintenance_interval_days", "INTEGER"),
                ("specifications", "TEXT" if is_sqlite else "JSONB"),
                ("documentation_url", "VARCHAR(500)"),
            ]
            
            for col_name, col_type in new_columns:
                if not column_exists(inspector, "equipment", col_name):
                    print(f"Adding column equipment.{col_name}...")
                    session.execute(text(f"ALTER TABLE equipment ADD COLUMN {col_name} {col_type}"))
                else:
                    print(f"Column equipment.{col_name} already exists, skipping...")
            
            # Create equipment_images table
            if not table_exists(inspector, "equipment_images"):
                print("Creating equipment_images table...")
                # Use SERIAL for PostgreSQL, INTEGER PRIMARY KEY for SQLite
                id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
                timestamp_default = "CURRENT_TIMESTAMP" if is_sqlite else "NOW()"
                bool_default = "0" if is_sqlite else "FALSE"
                
                session.execute(text(f"""
                    CREATE TABLE equipment_images (
                        id {id_type},
                        equipment_id INTEGER NOT NULL,
                        file_path VARCHAR(500) NOT NULL,
                        filename VARCHAR(255) NOT NULL,
                        original_filename VARCHAR(255),
                        mime_type VARCHAR(100),
                        file_size INTEGER,
                        caption VARCHAR(500),
                        is_primary BOOLEAN DEFAULT {bool_default},
                        uploaded_by VARCHAR(100),
                        created_at TIMESTAMP DEFAULT {timestamp_default}
                    )
                """))
                session.execute(text("CREATE INDEX idx_equipment_images_equipment ON equipment_images(equipment_id)"))
            else:
                print("Table equipment_images already exists, skipping...")
            
            # Create equipment_issues table
            if not table_exists(inspector, "equipment_issues"):
                print("Creating equipment_issues table...")
                id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
                timestamp_default = "CURRENT_TIMESTAMP" if is_sqlite else "NOW()"
                
                session.execute(text(f"""
                    CREATE TABLE equipment_issues (
                        id {id_type},
                        equipment_id INTEGER NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        category VARCHAR(50) DEFAULT 'other',
                        priority VARCHAR(20) DEFAULT 'medium',
                        status VARCHAR(50) DEFAULT 'open',
                        reporter_id INTEGER,
                        assignee_id INTEGER,
                        resolution TEXT,
                        cost NUMERIC(10, 2),
                        downtime_hours NUMERIC(10, 2),
                        created_at TIMESTAMP DEFAULT {timestamp_default},
                        updated_at TIMESTAMP DEFAULT {timestamp_default},
                        resolved_at TIMESTAMP
                    )
                """))
                session.execute(text("CREATE INDEX idx_equipment_issues_equipment ON equipment_issues(equipment_id)"))
                session.execute(text("CREATE INDEX idx_equipment_issues_status ON equipment_issues(status)"))
                session.execute(text("CREATE INDEX idx_equipment_issues_assignee ON equipment_issues(assignee_id)"))
            else:
                print("Table equipment_issues already exists, skipping...")
            
            # Create procedure_equipment table
            if not table_exists(inspector, "procedure_equipment"):
                print("Creating procedure_equipment table...")
                id_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "SERIAL PRIMARY KEY"
                bool_default = "1" if is_sqlite else "TRUE"
                
                session.execute(text(f"""
                    CREATE TABLE procedure_equipment (
                        id {id_type},
                        procedure_id INTEGER NOT NULL,
                        equipment_id INTEGER NOT NULL,
                        role VARCHAR(100),
                        is_required BOOLEAN DEFAULT {bool_default},
                        notes TEXT,
                        UNIQUE(procedure_id, equipment_id)
                    )
                """))
                session.execute(text("CREATE INDEX idx_procedure_equipment_procedure ON procedure_equipment(procedure_id)"))
                session.execute(text("CREATE INDEX idx_procedure_equipment_equipment ON procedure_equipment(equipment_id)"))
            else:
                print("Table procedure_equipment already exists, skipping...")
            
            # Add equipment_id to instruments table if not exists
            if table_exists(inspector, "instruments"):
                if not column_exists(inspector, "instruments", "equipment_id"):
                    print("Adding column instruments.equipment_id...")
                    session.execute(text("ALTER TABLE instruments ADD COLUMN equipment_id INTEGER"))
                else:
                    print("Column instruments.equipment_id already exists, skipping...")
            
            session.commit()
            print("\nMigration completed successfully!")
            return True
            
        except Exception as e:
            session.rollback()
            print(f"Migration failed: {e}")
            return False


if __name__ == "__main__":
    run_migration()
