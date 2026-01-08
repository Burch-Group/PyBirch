"""
Add Scan Logs Table Migration
=============================
Creates the scan_logs table for storing scan execution logs.

Run with:
    python database/migrations/add_scan_logs.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import create_engine, inspect, text


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate(db_path: str):
    """Run the migration to add scan_logs table."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Create scan_logs table
    if not check_table_exists(engine, 'scan_logs'):
        print("Creating scan_logs table...")
        
        create_table_sql = """
        CREATE TABLE scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            phase VARCHAR(50),
            level VARCHAR(20) DEFAULT 'INFO',
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            progress NUMERIC(5,2),
            extra_data JSON,
            FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("  ✓ scan_logs table created")
        
        # Create indexes
        print("Creating indexes...")
        indexes = [
            "CREATE INDEX idx_scan_logs_scan ON scan_logs(scan_id)",
            "CREATE INDEX idx_scan_logs_level ON scan_logs(level)",
            "CREATE INDEX idx_scan_logs_phase ON scan_logs(phase)",
            "CREATE INDEX idx_scan_logs_timestamp ON scan_logs(timestamp)",
        ]
        
        with engine.connect() as conn:
            for idx_sql in indexes:
                conn.execute(text(idx_sql))
            conn.commit()
        print("  ✓ Indexes created")
        
    else:
        print("scan_logs table already exists, skipping creation")
    
    print("\nMigration completed successfully!")
    return True


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='Add scan_logs table migration')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
