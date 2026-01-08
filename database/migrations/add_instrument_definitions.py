"""
Add Instrument Definitions Tables Migration
===========================================
Creates tables for storing instrument code in the database:
- instrument_definitions: Stores Python source code for instruments
- instrument_definition_versions: Version history for code changes
- computer_bindings: Links instruments to specific computers

Also adds definition_id column to instruments table.

Run with:
    python database/migrations/add_instrument_definitions.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, JSON, Boolean,
    ForeignKey, Index, inspect, text
)


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate(db_path: str):
    """Run the migration to add instrument definition tables."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # 1. Create instrument_definitions table
    if not check_table_exists(engine, 'instrument_definitions'):
        print("Creating instrument_definitions table...")
        
        create_definitions_sql = """
        CREATE TABLE instrument_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL UNIQUE,
            display_name VARCHAR(255) NOT NULL,
            description TEXT,
            instrument_type VARCHAR(50) NOT NULL,
            category VARCHAR(100),
            manufacturer VARCHAR(255),
            source_code TEXT NOT NULL,
            base_class VARCHAR(100) NOT NULL,
            dependencies JSON,
            settings_schema JSON,
            default_settings JSON,
            data_columns JSON,
            data_units JSON,
            position_column VARCHAR(100),
            position_units VARCHAR(50),
            lab_id INTEGER,
            version INTEGER DEFAULT 1,
            is_public BOOLEAN DEFAULT 0,
            is_builtin BOOLEAN DEFAULT 0,
            is_approved BOOLEAN DEFAULT 1,
            created_by VARCHAR(100),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lab_id) REFERENCES labs (id)
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_definitions_sql))
            conn.commit()
        
        # Create indexes
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_instrument_def_type ON instrument_definitions (instrument_type)",
            "CREATE INDEX IF NOT EXISTS idx_instrument_def_lab ON instrument_definitions (lab_id)",
            "CREATE INDEX IF NOT EXISTS idx_instrument_def_category ON instrument_definitions (category)",
        ]
        
        with engine.connect() as conn:
            for idx_sql in indexes_sql:
                conn.execute(text(idx_sql))
            conn.commit()
        
        print("  ✓ instrument_definitions table created")
    else:
        print("  Table 'instrument_definitions' already exists. Skipping.")
    
    # 2. Create instrument_definition_versions table
    if not check_table_exists(engine, 'instrument_definition_versions'):
        print("Creating instrument_definition_versions table...")
        
        create_versions_sql = """
        CREATE TABLE instrument_definition_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            definition_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            source_code TEXT NOT NULL,
            change_summary TEXT,
            created_by VARCHAR(100),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (definition_id) REFERENCES instrument_definitions (id) ON DELETE CASCADE,
            UNIQUE (definition_id, version)
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_versions_sql))
            conn.commit()
        
        # Create index
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_instrument_def_version_def ON instrument_definition_versions (definition_id)"))
            conn.commit()
        
        print("  ✓ instrument_definition_versions table created")
    else:
        print("  Table 'instrument_definition_versions' already exists. Skipping.")
    
    # 3. Create computer_bindings table
    if not check_table_exists(engine, 'computer_bindings'):
        print("Creating computer_bindings table...")
        
        create_bindings_sql = """
        CREATE TABLE computer_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instrument_id INTEGER NOT NULL,
            computer_name VARCHAR(255) NOT NULL,
            computer_id VARCHAR(255),
            username VARCHAR(100),
            adapter VARCHAR(255),
            adapter_type VARCHAR(50),
            is_primary BOOLEAN DEFAULT 1,
            last_connected DATETIME,
            last_settings JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (instrument_id) REFERENCES instruments (id) ON DELETE CASCADE,
            UNIQUE (instrument_id, computer_name)
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_bindings_sql))
            conn.commit()
        
        # Create indexes
        indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_computer_binding_computer ON computer_bindings (computer_name)",
            "CREATE INDEX IF NOT EXISTS idx_computer_binding_instrument ON computer_bindings (instrument_id)",
        ]
        
        with engine.connect() as conn:
            for idx_sql in indexes_sql:
                conn.execute(text(idx_sql))
            conn.commit()
        
        print("  ✓ computer_bindings table created")
    else:
        print("  Table 'computer_bindings' already exists. Skipping.")
    
    # 4. Add definition_id column to instruments table
    if check_table_exists(engine, 'instruments'):
        if not check_column_exists(engine, 'instruments', 'definition_id'):
            print("Adding definition_id column to instruments table...")
            
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE instruments ADD COLUMN definition_id INTEGER REFERENCES instrument_definitions(id)"))
                conn.commit()
            
            print("  ✓ definition_id column added to instruments")
        else:
            print("  Column 'definition_id' already exists in instruments. Skipping.")
    
    print("\nMigration completed successfully!")
    return True


def rollback(db_path: str):
    """Rollback the migration by dropping the tables."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    engine = create_engine(f'sqlite:///{db_path}')
    
    print("Rolling back instrument definitions migration...")
    
    with engine.connect() as conn:
        # Drop tables in reverse order (respecting foreign keys)
        conn.execute(text("DROP TABLE IF EXISTS computer_bindings"))
        conn.execute(text("DROP TABLE IF EXISTS instrument_definition_versions"))
        conn.execute(text("DROP TABLE IF EXISTS instrument_definitions"))
        conn.commit()
    
    print("  ✓ Tables dropped")
    
    # Note: SQLite doesn't support DROP COLUMN easily, so we skip removing definition_id
    print("  Note: definition_id column in instruments table was not removed (SQLite limitation)")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Instrument Definitions Migration")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback(args.db)
    else:
        migrate(args.db)
