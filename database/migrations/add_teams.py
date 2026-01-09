"""
Add Teams Tables Migration
==========================
Creates the teams, team_members, and team_access tables for group-based permissions.

Run with:
    python database/migrations/add_teams.py --db database/pybirch.db
"""

import sys
import os

from sqlalchemy import create_engine, inspect, text


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate(db_path: str):
    """Run the migration to add teams, team_members, and team_access tables."""
    if not db_path:
        print("Error: Database path required. Use --db <path>")
        return False
    
    # Create engine directly
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Create teams table
    if not check_table_exists(engine, 'teams'):
        print("Creating teams table...")
        
        create_table_sql = """
        CREATE TABLE teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_id INTEGER NOT NULL,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(20),
            description TEXT,
            color VARCHAR(20) DEFAULT '#6366f1',
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(100),
            trashed_at DATETIME,
            trashed_by VARCHAR(100),
            FOREIGN KEY (lab_id) REFERENCES labs (id) ON DELETE CASCADE
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("  ✓ teams table created")
        
        # Create indexes
        print("Creating teams indexes...")
        indexes = [
            "CREATE INDEX idx_teams_lab ON teams(lab_id)",
            "CREATE UNIQUE INDEX idx_teams_lab_name ON teams(lab_id, name)",
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
        print("teams table already exists, skipping...")
    
    # Create team_members table
    if not check_table_exists(engine, 'team_members'):
        print("Creating team_members table...")
        
        create_table_sql = """
        CREATE TABLE team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            lab_member_id INTEGER NOT NULL,
            role VARCHAR(50) DEFAULT 'member',
            is_active BOOLEAN DEFAULT 1,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            left_at DATETIME,
            notes TEXT,
            FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE,
            FOREIGN KEY (lab_member_id) REFERENCES lab_members (id) ON DELETE CASCADE
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("  ✓ team_members table created")
        
        # Create indexes
        print("Creating team_members indexes...")
        indexes = [
            "CREATE INDEX idx_team_members_team ON team_members(team_id)",
            "CREATE INDEX idx_team_members_lab_member ON team_members(lab_member_id)",
            "CREATE UNIQUE INDEX uq_team_member ON team_members(team_id, lab_member_id)",
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
        print("team_members table already exists, skipping...")
    
    # Create team_access table
    if not check_table_exists(engine, 'team_access'):
        print("Creating team_access table...")
        
        create_table_sql = """
        CREATE TABLE team_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER NOT NULL,
            access_level VARCHAR(20) DEFAULT 'view',
            granted_by VARCHAR(100),
            granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            is_active BOOLEAN DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
        )
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
        print("  ✓ team_access table created")
        
        # Create indexes
        print("Creating team_access indexes...")
        indexes = [
            "CREATE INDEX idx_team_access_team ON team_access(team_id)",
            "CREATE INDEX idx_team_access_entity ON team_access(entity_type, entity_id)",
            "CREATE UNIQUE INDEX uq_team_entity_access ON team_access(team_id, entity_type, entity_id)",
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
        print("team_access table already exists, skipping...")
    
    print("\nMigration complete!")
    return True


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Add teams tables to database')
    parser.add_argument('--db', type=str, required=True, help='Path to SQLite database')
    
    args = parser.parse_args()
    
    success = migrate(args.db)
    sys.exit(0 if success else 1)
