"""
Add Instrument Definition Issues Table Migration
================================================
Creates the instrument_definition_issues table for tracking issues related to instrument definitions.

Run with:
    python database/migrations/add_instrument_definition_issues.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import create_engine, inspect, text


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate(db_path: str):
    """Run the migration to add instrument_definition_issues table."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Create instrument_definition_issues table
    if not check_table_exists(engine, 'instrument_definition_issues'):
        print("Creating instrument_definition_issues table...")
        
        create_table_sql = """
        CREATE TABLE instrument_definition_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            definition_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            category VARCHAR(50) DEFAULT 'bug',
            priority VARCHAR(20) DEFAULT 'medium',
            status VARCHAR(20) DEFAULT 'open',
            reporter_id INTEGER,
            assignee_id INTEGER,
            error_message TEXT,
            steps_to_reproduce TEXT,
            affected_version VARCHAR(50),
            fixed_in_version VARCHAR(50),
            environment_info TEXT,
            resolution TEXT,
            resolution_steps TEXT,
            resolved_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (definition_id) REFERENCES instrument_definitions (id) ON DELETE CASCADE,
            FOREIGN KEY (reporter_id) REFERENCES users (id) ON DELETE SET NULL,
            FOREIGN KEY (assignee_id) REFERENCES users (id) ON DELETE SET NULL
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("  ✓ instrument_definition_issues table created")
        
        # Create indexes
        print("Creating indexes...")
        indexes = [
            "CREATE INDEX idx_definition_issues_definition ON instrument_definition_issues(definition_id)",
            "CREATE INDEX idx_definition_issues_status ON instrument_definition_issues(status)",
            "CREATE INDEX idx_definition_issues_priority ON instrument_definition_issues(priority)",
            "CREATE INDEX idx_definition_issues_category ON instrument_definition_issues(category)",
            "CREATE INDEX idx_definition_issues_reporter ON instrument_definition_issues(reporter_id)",
            "CREATE INDEX idx_definition_issues_assignee ON instrument_definition_issues(assignee_id)",
            "CREATE INDEX idx_definition_issues_created ON instrument_definition_issues(created_at)",
        ]
        
        with engine.connect() as conn:
            for idx_sql in indexes:
                conn.execute(text(idx_sql))
            conn.commit()
        print("  ✓ Indexes created")
        
    else:
        print("instrument_definition_issues table already exists, skipping creation")
    
    print("\nMigration completed successfully!")
    return True


def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description='Add instrument_definition_issues table migration')
    parser.add_argument('--db', required=True, help='Path to SQLite database file')
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
