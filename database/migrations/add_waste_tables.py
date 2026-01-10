"""
Migration: Add Waste and WastePrecursor tables
================================================
Creates the wastes table for tracking hazardous waste containers and
the waste_precursors junction table linking waste to source precursors.

Works with both SQLite and PostgreSQL.

Run with: python -m database.migrations.add_waste_tables
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
            # Create wastes table
            if not table_exists(inspector, 'wastes'):
                print("Creating wastes table...")
                if is_sqlite:
                    session.execute(text("""
                        CREATE TABLE wastes (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lab_id INTEGER NOT NULL,
                            project_id INTEGER,
                            owner_id INTEGER,
                            name VARCHAR(255) NOT NULL,
                            waste_type VARCHAR(50) DEFAULT 'mixed',
                            hazard_class VARCHAR(50),
                            container_type VARCHAR(50),
                            container_size VARCHAR(50),
                            current_fill_percent FLOAT DEFAULT 0,
                            fill_status VARCHAR(20) DEFAULT 'empty',
                            status VARCHAR(50) DEFAULT 'active',
                            contents_description TEXT,
                            contains_chemicals TEXT,
                            ph_range VARCHAR(50),
                            epa_waste_code VARCHAR(50),
                            un_number VARCHAR(50),
                            sds_reference VARCHAR(255),
                            special_handling TEXT,
                            opened_date DATE,
                            full_date DATE,
                            collection_requested_date DATE,
                            collected_date DATE,
                            disposal_date DATE,
                            disposal_vendor VARCHAR(255),
                            manifest_number VARCHAR(100),
                            notes TEXT,
                            extra_data TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(255),
                            is_archived BOOLEAN DEFAULT 0,
                            archived_at TIMESTAMP,
                            archived_by VARCHAR(255),
                            is_trashed BOOLEAN DEFAULT 0,
                            trashed_at TIMESTAMP,
                            trashed_by VARCHAR(255),
                            FOREIGN KEY (lab_id) REFERENCES labs(id),
                            FOREIGN KEY (project_id) REFERENCES projects(id),
                            FOREIGN KEY (owner_id) REFERENCES users(id)
                        )
                    """))
                else:
                    # PostgreSQL version
                    session.execute(text("""
                        CREATE TABLE wastes (
                            id SERIAL PRIMARY KEY,
                            lab_id INTEGER NOT NULL REFERENCES labs(id),
                            project_id INTEGER REFERENCES projects(id),
                            owner_id INTEGER REFERENCES users(id),
                            name VARCHAR(255) NOT NULL,
                            waste_type VARCHAR(50) DEFAULT 'mixed',
                            hazard_class VARCHAR(50),
                            container_type VARCHAR(50),
                            container_size VARCHAR(50),
                            current_fill_percent FLOAT DEFAULT 0,
                            fill_status VARCHAR(20) DEFAULT 'empty',
                            status VARCHAR(50) DEFAULT 'active',
                            contents_description TEXT,
                            contains_chemicals TEXT,
                            ph_range VARCHAR(50),
                            epa_waste_code VARCHAR(50),
                            un_number VARCHAR(50),
                            sds_reference VARCHAR(255),
                            special_handling TEXT,
                            opened_date DATE,
                            full_date DATE,
                            collection_requested_date DATE,
                            collected_date DATE,
                            disposal_date DATE,
                            disposal_vendor VARCHAR(255),
                            manifest_number VARCHAR(100),
                            notes TEXT,
                            extra_data JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(255),
                            is_archived BOOLEAN DEFAULT FALSE,
                            archived_at TIMESTAMP,
                            archived_by VARCHAR(255),
                            is_trashed BOOLEAN DEFAULT FALSE,
                            trashed_at TIMESTAMP,
                            trashed_by VARCHAR(255)
                        )
                    """))
                print("  ✓ Created wastes table")
            else:
                print("  - wastes table already exists")
            
            # Create waste_precursors junction table
            if not table_exists(inspector, 'waste_precursors'):
                print("Creating waste_precursors table...")
                if is_sqlite:
                    session.execute(text("""
                        CREATE TABLE waste_precursors (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            waste_id INTEGER NOT NULL,
                            precursor_id INTEGER NOT NULL,
                            quantity_used VARCHAR(100),
                            notes TEXT,
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            added_by VARCHAR(255),
                            FOREIGN KEY (waste_id) REFERENCES wastes(id) ON DELETE CASCADE,
                            FOREIGN KEY (precursor_id) REFERENCES precursors(id) ON DELETE CASCADE,
                            UNIQUE(waste_id, precursor_id)
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE waste_precursors (
                            id SERIAL PRIMARY KEY,
                            waste_id INTEGER NOT NULL REFERENCES wastes(id) ON DELETE CASCADE,
                            precursor_id INTEGER NOT NULL REFERENCES precursors(id) ON DELETE CASCADE,
                            quantity_used VARCHAR(100),
                            notes TEXT,
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            added_by VARCHAR(255),
                            UNIQUE(waste_id, precursor_id)
                        )
                    """))
                print("  ✓ Created waste_precursors table")
            else:
                print("  - waste_precursors table already exists")
            
            # Create indexes
            print("Creating indexes...")
            try:
                session.execute(text("CREATE INDEX idx_wastes_lab_id ON wastes(lab_id)"))
                print("  ✓ Created idx_wastes_lab_id")
            except Exception:
                print("  - idx_wastes_lab_id already exists")
            
            try:
                session.execute(text("CREATE INDEX idx_wastes_project_id ON wastes(project_id)"))
                print("  ✓ Created idx_wastes_project_id")
            except Exception:
                print("  - idx_wastes_project_id already exists")
            
            try:
                session.execute(text("CREATE INDEX idx_wastes_owner_id ON wastes(owner_id)"))
                print("  ✓ Created idx_wastes_owner_id")
            except Exception:
                print("  - idx_wastes_owner_id already exists")
            
            try:
                session.execute(text("CREATE INDEX idx_wastes_status ON wastes(status)"))
                print("  ✓ Created idx_wastes_status")
            except Exception:
                print("  - idx_wastes_status already exists")
            
            try:
                session.execute(text("CREATE INDEX idx_wastes_fill_status ON wastes(fill_status)"))
                print("  ✓ Created idx_wastes_fill_status")
            except Exception:
                print("  - idx_wastes_fill_status already exists")
            
            try:
                session.execute(text("CREATE INDEX idx_waste_precursors_waste_id ON waste_precursors(waste_id)"))
                print("  ✓ Created idx_waste_precursors_waste_id")
            except Exception:
                print("  - idx_waste_precursors_waste_id already exists")
            
            try:
                session.execute(text("CREATE INDEX idx_waste_precursors_precursor_id ON waste_precursors(precursor_id)"))
                print("  ✓ Created idx_waste_precursors_precursor_id")
            except Exception:
                print("  - idx_waste_precursors_precursor_id already exists")
            
            session.commit()
            print("\n✓ Migration completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"\n✗ Migration failed: {e}")
            raise


def migrate_down(db_path: str = None):
    """Rollback the migration."""
    if db_path:
        os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"
    
    db = DatabaseManager(create_tables=False)
    inspector = inspect(db.engine)
    
    print(f"Rolling back migration on database: {db.database_url}")
    
    with db.session() as session:
        try:
            # Drop junction table first (foreign key dependency)
            if table_exists(inspector, 'waste_precursors'):
                print("Dropping waste_precursors table...")
                session.execute(text("DROP TABLE waste_precursors"))
                print("  ✓ Dropped waste_precursors table")
            
            # Drop main table
            if table_exists(inspector, 'wastes'):
                print("Dropping wastes table...")
                session.execute(text("DROP TABLE wastes"))
                print("  ✓ Dropped wastes table")
            
            session.commit()
            print("\n✓ Rollback completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"\n✗ Rollback failed: {e}")
            raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Waste tables migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    parser.add_argument('--db', type=str, help='Path to SQLite database file')
    
    args = parser.parse_args()
    
    if args.rollback:
        migrate_down(args.db)
    else:
        migrate_up(args.db)
