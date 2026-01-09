"""
Add Page Views Table Migration
==============================
Creates the page_views table for tracking page views and time-on-page analytics.

Run with:
    python database/migrations/add_page_views.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import create_engine, inspect, text


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate(db_path: str):
    """Run the migration to add page_views table."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Create page_views table
    if not check_table_exists(engine, 'page_views'):
        print("Creating page_views table...")
        
        create_table_sql = """
        CREATE TABLE page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            page_path VARCHAR(500) NOT NULL,
            page_title VARCHAR(255),
            referrer VARCHAR(500),
            duration_seconds INTEGER,
            viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id VARCHAR(100),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("  ✓ page_views table created")
        
        # Create indexes
        print("Creating indexes...")
        indexes = [
            "CREATE INDEX idx_page_views_user ON page_views(user_id)",
            "CREATE INDEX idx_page_views_path ON page_views(page_path)",
            "CREATE INDEX idx_page_views_timestamp ON page_views(viewed_at)",
            "CREATE INDEX idx_page_views_session ON page_views(session_id)",
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
        print("page_views table already exists, skipping...")
    
    print("\nMigration complete!")
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Add page_views table migration')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)
