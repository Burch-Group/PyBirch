"""
Add QR Code Scans Table Migration
=================================
Creates the qr_code_scans table for tracking QR code scan analytics.

Run with:
    python database/migrations/add_qr_code_scans.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import create_engine, inspect, text


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate(db_path: str):
    """Run the migration to add qr_code_scans table."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Create qr_code_scans table
    if not check_table_exists(engine, 'qr_code_scans'):
        print("Creating qr_code_scans table...")
        
        create_table_sql = """
        CREATE TABLE qr_code_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER NOT NULL,
            scanned_url VARCHAR(500),
            scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("  ✓ qr_code_scans table created")
        
        # Create indexes
        print("Creating indexes...")
        indexes = [
            "CREATE INDEX idx_qr_scans_user ON qr_code_scans(user_id)",
            "CREATE INDEX idx_qr_scans_entity ON qr_code_scans(entity_type, entity_id)",
            "CREATE INDEX idx_qr_scans_timestamp ON qr_code_scans(scanned_at)",
        ]
        
        with engine.connect() as conn:
            for idx_sql in indexes:
                try:
                    conn.execute(text(idx_sql))
                    print(f"  ✓ Index created")
                except Exception as e:
                    print(f"  ! Index might already exist: {e}")
            conn.commit()
    else:
        print("qr_code_scans table already exists, skipping...")
    
    print("\n✅ Migration complete!")
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Add QR code scans table')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)
