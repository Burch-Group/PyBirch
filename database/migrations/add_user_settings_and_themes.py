"""
Migration: Add user settings and themes tables
Created: 2026-01-09

Adds:
- user_settings table for storing user preferences including theme settings
- user_themes table for storing custom user-defined themes

This supports the new settings page with:
- Light/dark/system theme mode selection
- Custom theme creation with light and dark palettes
- General user preferences (compact tables, notifications, etc.)
"""

import sys
import os

# Add parent directories to path for imports
migrations_dir = os.path.dirname(os.path.abspath(__file__))
database_dir = os.path.dirname(migrations_dir)
project_dir = os.path.dirname(database_dir)
sys.path.insert(0, project_dir)
sys.path.insert(0, database_dir)

from sqlalchemy import create_engine, text, inspect

def get_db_path():
    """Get the database path."""
    # Try to import from session module
    try:
        from database.session import get_db_path as _get_db_path
        return _get_db_path()
    except ImportError:
        pass
    
    # Fallback: look for database file in standard locations
    possible_paths = [
        os.path.join(database_dir, 'pybirch.db'),
        os.path.join(project_dir, 'pybirch.db'),
        os.path.join(os.path.expanduser('~'), '.pybirch', 'pybirch.db'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Default path
    return os.path.join(database_dir, 'pybirch.db')


def check_table_exists(engine, table_name):
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return False
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in columns


def migrate(db_path=None):
    """Run the migration to add user settings and themes tables."""
    if db_path is None:
        db_path = get_db_path()
    
    engine = create_engine(f'sqlite:///{db_path}')
    
    with engine.connect() as conn:
        # Create user_themes table first (referenced by user_settings)
        if not check_table_exists(engine, 'user_themes'):
            print("Creating user_themes table...")
            conn.execute(text('''
                CREATE TABLE user_themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    light_palette JSON NOT NULL DEFAULT '{}',
                    dark_palette JSON NOT NULL DEFAULT '{}',
                    is_public BOOLEAN DEFAULT 0,
                    is_default BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE (user_id, name)
                )
            '''))
            conn.execute(text('CREATE INDEX idx_user_themes_user ON user_themes(user_id)'))
            conn.execute(text('CREATE INDEX idx_user_themes_public ON user_themes(is_public)'))
            print("  Created user_themes table with indexes")
        else:
            print("user_themes table already exists")
        
        # Create user_settings table
        if not check_table_exists(engine, 'user_settings'):
            print("Creating user_settings table...")
            conn.execute(text('''
                CREATE TABLE user_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    theme_mode VARCHAR(20) DEFAULT 'system',
                    active_theme_id INTEGER,
                    settings JSON DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (active_theme_id) REFERENCES user_themes(id) ON DELETE SET NULL
                )
            '''))
            print("  Created user_settings table")
        else:
            print("user_settings table already exists")
        
        conn.commit()
    
    print("\nMigration completed successfully!")
    print("\nNew tables:")
    print("  - user_settings: Stores user preferences and theme mode")
    print("  - user_themes: Stores custom color themes with light/dark palettes")


def rollback(db_path=None):
    """Rollback the migration by dropping the tables."""
    if db_path is None:
        db_path = get_db_path()
    
    engine = create_engine(f'sqlite:///{db_path}')
    
    with engine.connect() as conn:
        # Drop user_settings first (has foreign key to user_themes)
        if check_table_exists(engine, 'user_settings'):
            print("Dropping user_settings table...")
            conn.execute(text('DROP TABLE user_settings'))
        
        if check_table_exists(engine, 'user_themes'):
            print("Dropping user_themes table...")
            conn.execute(text('DROP TABLE user_themes'))
        
        conn.commit()
    
    print("Rollback completed successfully!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Add user settings and themes tables')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    parser.add_argument('--db-path', type=str, help='Path to the database file')
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback(args.db_path)
    else:
        migrate(args.db_path)
