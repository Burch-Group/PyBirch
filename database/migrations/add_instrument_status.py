"""
Add InstrumentStatus Table Migration
====================================
Creates the instrument_status table for real-time instrument status tracking.

This migration adds:
- instrument_status table with status tracking fields
- Relationships to the instruments table
- Indexes for efficient querying

Run with:
    python database/migrations/add_instrument_status.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey, Index,
    inspect, text
)


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate(db_path: str):
    """Run the migration to add instrument_status table."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Check if table already exists
    if check_table_exists(engine, 'instrument_status'):
        print("Table 'instrument_status' already exists. Skipping migration.")
        return True
    
    print("Creating instrument_status table...")
    
    # Create the table using raw SQL for more control
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS instrument_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instrument_id INTEGER NOT NULL,
        status VARCHAR(50) DEFAULT 'disconnected',
        last_connected DATETIME,
        current_settings JSON,
        error_message TEXT,
        error_traceback TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (instrument_id) REFERENCES instruments (id) ON DELETE CASCADE
    )
    """
    
    # Create indexes
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_instrument_status_instrument ON instrument_status (instrument_id)",
        "CREATE INDEX IF NOT EXISTS idx_instrument_status_status ON instrument_status (status)",
        "CREATE INDEX IF NOT EXISTS idx_instrument_status_updated ON instrument_status (updated_at)",
    ]
    
    try:
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            for index_sql in create_indexes_sql:
                conn.execute(text(index_sql))
            conn.commit()
        
        print("Successfully created instrument_status table with indexes.")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False


def rollback(db_path: str):
    """Rollback the migration by dropping the instrument_status table."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    engine = create_engine(f'sqlite:///{db_path}')
    
    if not check_table_exists(engine, 'instrument_status'):
        print("Table 'instrument_status' does not exist. Nothing to rollback.")
        return True
    
    print("Dropping instrument_status table...")
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS instrument_status"))
            conn.commit()
        
        print("Successfully dropped instrument_status table.")
        return True
        
    except Exception as e:
        print(f"Error during rollback: {e}")
        return False


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='InstrumentStatus table migration')
    parser.add_argument('--db', type=str, required=True, help='Path to database file')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    
    args = parser.parse_args()
    
    if args.rollback:
        success = rollback(args.db)
    else:
        success = migrate(args.db)
    
    sys.exit(0 if success else 1)
