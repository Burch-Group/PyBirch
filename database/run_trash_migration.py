"""
Script to run the trash columns migration.
Run this once to add trashed_at and trashed_by columns to all trashable entities.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.session import init_db
from database.migrations.add_trash_columns import migrate


def main():
    """Run the trash columns migration."""
    print("Initializing database connection...")
    db = init_db()
    
    print("Running trash columns migration...")
    migrate(db.engine)
    
    print("\nMigration complete!")


if __name__ == '__main__':
    main()
