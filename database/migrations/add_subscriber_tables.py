"""
Migration: Add Subscriber and Notification tables
==================================================
Creates the subscribers, notification_rules, and notification_logs tables
for the pub/sub notification system.

Works with both SQLite and PostgreSQL.

Run with: python -m database.migrations.add_subscriber_tables
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
            # Create subscribers table
            if not table_exists(inspector, 'subscribers'):
                print("Creating subscribers table...")
                if is_sqlite:
                    session.execute(text("""
                        CREATE TABLE subscribers (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lab_id INTEGER NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            channel_type VARCHAR(50) NOT NULL,
                            channel_address VARCHAR(500),
                            user_id INTEGER,
                            slack_workspace_id VARCHAR(100),
                            slack_channel_id VARCHAR(100),
                            webhook_url VARCHAR(1000),
                            webhook_headers TEXT,
                            is_verified BOOLEAN DEFAULT 0,
                            is_active BOOLEAN DEFAULT 1,
                            failure_count INTEGER DEFAULT 0,
                            last_failure_at TIMESTAMP,
                            last_failure_reason TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by_id INTEGER,
                            is_trashed BOOLEAN DEFAULT 0,
                            trashed_at TIMESTAMP,
                            trashed_by VARCHAR(255),
                            FOREIGN KEY (lab_id) REFERENCES labs(id),
                            FOREIGN KEY (user_id) REFERENCES users(id),
                            FOREIGN KEY (created_by_id) REFERENCES users(id)
                        )
                    """))
                else:
                    # PostgreSQL
                    session.execute(text("""
                        CREATE TABLE subscribers (
                            id SERIAL PRIMARY KEY,
                            lab_id INTEGER NOT NULL REFERENCES labs(id),
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            channel_type VARCHAR(50) NOT NULL,
                            channel_address VARCHAR(500),
                            user_id INTEGER REFERENCES users(id),
                            slack_workspace_id VARCHAR(100),
                            slack_channel_id VARCHAR(100),
                            webhook_url VARCHAR(1000),
                            webhook_headers JSONB,
                            is_verified BOOLEAN DEFAULT false,
                            is_active BOOLEAN DEFAULT true,
                            failure_count INTEGER DEFAULT 0,
                            last_failure_at TIMESTAMP,
                            last_failure_reason TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by_id INTEGER REFERENCES users(id),
                            is_trashed BOOLEAN DEFAULT false,
                            trashed_at TIMESTAMP,
                            trashed_by VARCHAR(255)
                        )
                    """))
                print("  Created subscribers table")
            else:
                print("  subscribers table already exists")
            
            # Create notification_rules table
            if not table_exists(inspector, 'notification_rules'):
                print("Creating notification_rules table...")
                if is_sqlite:
                    session.execute(text("""
                        CREATE TABLE notification_rules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            subscriber_id INTEGER NOT NULL,
                            name VARCHAR(255),
                            description TEXT,
                            event_type VARCHAR(100) NOT NULL,
                            project_id INTEGER,
                            owner_only BOOLEAN DEFAULT 0,
                            conditions TEXT,
                            custom_message_template TEXT,
                            is_active BOOLEAN DEFAULT 1,
                            priority INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by_id INTEGER,
                            is_trashed BOOLEAN DEFAULT 0,
                            trashed_at TIMESTAMP,
                            trashed_by VARCHAR(255),
                            FOREIGN KEY (subscriber_id) REFERENCES subscribers(id),
                            FOREIGN KEY (project_id) REFERENCES projects(id),
                            FOREIGN KEY (created_by_id) REFERENCES users(id)
                        )
                    """))
                else:
                    # PostgreSQL
                    session.execute(text("""
                        CREATE TABLE notification_rules (
                            id SERIAL PRIMARY KEY,
                            subscriber_id INTEGER NOT NULL REFERENCES subscribers(id),
                            name VARCHAR(255),
                            description TEXT,
                            event_type VARCHAR(100) NOT NULL,
                            project_id INTEGER REFERENCES projects(id),
                            owner_only BOOLEAN DEFAULT false,
                            conditions JSONB,
                            custom_message_template TEXT,
                            is_active BOOLEAN DEFAULT true,
                            priority INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by_id INTEGER REFERENCES users(id),
                            is_trashed BOOLEAN DEFAULT false,
                            trashed_at TIMESTAMP,
                            trashed_by VARCHAR(255)
                        )
                    """))
                print("  Created notification_rules table")
            else:
                print("  notification_rules table already exists")
            
            # Create notification_logs table
            if not table_exists(inspector, 'notification_logs'):
                print("Creating notification_logs table...")
                if is_sqlite:
                    session.execute(text("""
                        CREATE TABLE notification_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            subscriber_id INTEGER NOT NULL,
                            rule_id INTEGER,
                            event_type VARCHAR(100) NOT NULL,
                            entity_type VARCHAR(50),
                            entity_id INTEGER,
                            event_data TEXT,
                            message_content TEXT,
                            status VARCHAR(20) DEFAULT 'pending',
                            error_message TEXT,
                            retry_count INTEGER DEFAULT 0,
                            sent_at TIMESTAMP,
                            delivered_at TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (subscriber_id) REFERENCES subscribers(id),
                            FOREIGN KEY (rule_id) REFERENCES notification_rules(id)
                        )
                    """))
                else:
                    # PostgreSQL
                    session.execute(text("""
                        CREATE TABLE notification_logs (
                            id SERIAL PRIMARY KEY,
                            subscriber_id INTEGER NOT NULL REFERENCES subscribers(id),
                            rule_id INTEGER REFERENCES notification_rules(id),
                            event_type VARCHAR(100) NOT NULL,
                            entity_type VARCHAR(50),
                            entity_id INTEGER,
                            event_data JSONB,
                            message_content TEXT,
                            status VARCHAR(20) DEFAULT 'pending',
                            error_message TEXT,
                            retry_count INTEGER DEFAULT 0,
                            sent_at TIMESTAMP,
                            delivered_at TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                print("  Created notification_logs table")
            else:
                print("  notification_logs table already exists")
            
            # Create indexes for performance
            print("Creating indexes...")
            
            # Subscribers indexes
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_subscribers_lab_id ON subscribers(lab_id)
                """))
                print("  Created idx_subscribers_lab_id")
            except Exception as e:
                print(f"  Index idx_subscribers_lab_id may already exist: {e}")
            
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_subscribers_user_id ON subscribers(user_id)
                """))
                print("  Created idx_subscribers_user_id")
            except Exception as e:
                print(f"  Index idx_subscribers_user_id may already exist: {e}")
            
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_subscribers_channel_type ON subscribers(channel_type)
                """))
                print("  Created idx_subscribers_channel_type")
            except Exception as e:
                print(f"  Index idx_subscribers_channel_type may already exist: {e}")
            
            # Notification rules indexes
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_notification_rules_subscriber_id ON notification_rules(subscriber_id)
                """))
                print("  Created idx_notification_rules_subscriber_id")
            except Exception as e:
                print(f"  Index idx_notification_rules_subscriber_id may already exist: {e}")
            
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_notification_rules_event_type ON notification_rules(event_type)
                """))
                print("  Created idx_notification_rules_event_type")
            except Exception as e:
                print(f"  Index idx_notification_rules_event_type may already exist: {e}")
            
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_notification_rules_project_id ON notification_rules(project_id)
                """))
                print("  Created idx_notification_rules_project_id")
            except Exception as e:
                print(f"  Index idx_notification_rules_project_id may already exist: {e}")
            
            # Notification logs indexes
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_notification_logs_subscriber_id ON notification_logs(subscriber_id)
                """))
                print("  Created idx_notification_logs_subscriber_id")
            except Exception as e:
                print(f"  Index idx_notification_logs_subscriber_id may already exist: {e}")
            
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_notification_logs_status ON notification_logs(status)
                """))
                print("  Created idx_notification_logs_status")
            except Exception as e:
                print(f"  Index idx_notification_logs_status may already exist: {e}")
            
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at ON notification_logs(created_at)
                """))
                print("  Created idx_notification_logs_created_at")
            except Exception as e:
                print(f"  Index idx_notification_logs_created_at may already exist: {e}")
            
            session.commit()
            print("\nMigration completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"\nMigration failed: {e}")
            raise


def migrate_down(db_path: str = None):
    """Reverse the migration (drop tables)."""
    if db_path:
        os.environ['DATABASE_URL'] = f"sqlite:///{db_path}"
    
    db = DatabaseManager(create_tables=False)
    
    print(f"Rolling back migration on: {db.database_url}")
    
    with db.session() as session:
        try:
            # Drop tables in correct order (logs first, then rules, then subscribers)
            print("Dropping notification_logs table...")
            session.execute(text("DROP TABLE IF EXISTS notification_logs"))
            
            print("Dropping notification_rules table...")
            session.execute(text("DROP TABLE IF EXISTS notification_rules"))
            
            print("Dropping subscribers table...")
            session.execute(text("DROP TABLE IF EXISTS subscribers"))
            
            session.commit()
            print("Rollback completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"Rollback failed: {e}")
            raise


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Add subscriber and notification tables')
    parser.add_argument('--db', help='Database path (for SQLite) or connection string')
    parser.add_argument('--down', action='store_true', help='Rollback the migration')
    
    args = parser.parse_args()
    
    if args.down:
        migrate_down(args.db)
    else:
        migrate_up(args.db)
