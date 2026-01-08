"""
Migration script to standardize all owner/operator fields to 'created_by'.

This renames:
- scans.owner -> scans.created_by
- queues.operator -> queues.created_by
- fabrication_runs.operator -> fabrication_runs.created_by
- analyses.operator -> analyses.created_by

Run this once to update existing databases.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.session import init_db


def check_column_exists(session, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    try:
        session.execute(text(f"SELECT {column} FROM {table} LIMIT 1"))
        return True
    except Exception:
        return False


def rename_column_sqlite(session, table: str, old_col: str, new_col: str):
    """
    Rename a column in SQLite.
    SQLite 3.25+ supports ALTER TABLE RENAME COLUMN.
    For older versions, we'd need to recreate the table.
    """
    try:
        session.execute(text(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}"))
        session.commit()
        print(f"✓ Renamed {table}.{old_col} -> {new_col}")
        return True
    except Exception as e:
        print(f"  Error renaming {table}.{old_col}: {e}")
        session.rollback()
        return False


def migrate():
    """Standardize all owner/operator fields to created_by."""
    print("\n=== Standardizing created_by fields ===\n")
    
    db = init_db()
    
    with db.session() as session:
        # Scans: owner -> created_by
        if check_column_exists(session, 'scans', 'owner'):
            if check_column_exists(session, 'scans', 'created_by'):
                print("! scans.created_by already exists, copying data from owner")
                try:
                    session.execute(text("UPDATE scans SET created_by = owner WHERE created_by IS NULL AND owner IS NOT NULL"))
                    session.commit()
                    print("✓ Copied scans.owner data to created_by")
                except Exception as e:
                    print(f"  Error copying data: {e}")
                    session.rollback()
            else:
                rename_column_sqlite(session, 'scans', 'owner', 'created_by')
        elif check_column_exists(session, 'scans', 'created_by'):
            print("✓ scans.created_by already exists (owner already renamed)")
        else:
            print("! Neither scans.owner nor scans.created_by exists, adding created_by")
            try:
                session.execute(text("ALTER TABLE scans ADD COLUMN created_by VARCHAR(100)"))
                session.commit()
                print("✓ Added scans.created_by column")
            except Exception as e:
                print(f"  Error adding column: {e}")
                session.rollback()
        
        # Queues: operator -> created_by
        if check_column_exists(session, 'queues', 'operator'):
            if check_column_exists(session, 'queues', 'created_by'):
                print("! queues.created_by already exists, copying data from operator")
                try:
                    session.execute(text("UPDATE queues SET created_by = operator WHERE created_by IS NULL AND operator IS NOT NULL"))
                    session.commit()
                    print("✓ Copied queues.operator data to created_by")
                except Exception as e:
                    print(f"  Error copying data: {e}")
                    session.rollback()
            else:
                rename_column_sqlite(session, 'queues', 'operator', 'created_by')
        elif check_column_exists(session, 'queues', 'created_by'):
            print("✓ queues.created_by already exists (operator already renamed)")
        else:
            print("! Neither queues.operator nor queues.created_by exists, adding created_by")
            try:
                session.execute(text("ALTER TABLE queues ADD COLUMN created_by VARCHAR(100)"))
                session.commit()
                print("✓ Added queues.created_by column")
            except Exception as e:
                print(f"  Error adding column: {e}")
                session.rollback()
        
        # Fabrication Runs: operator -> created_by
        if check_column_exists(session, 'fabrication_runs', 'operator'):
            if check_column_exists(session, 'fabrication_runs', 'created_by'):
                print("! fabrication_runs.created_by already exists, copying data from operator")
                try:
                    session.execute(text("UPDATE fabrication_runs SET created_by = operator WHERE created_by IS NULL AND operator IS NOT NULL"))
                    session.commit()
                    print("✓ Copied fabrication_runs.operator data to created_by")
                except Exception as e:
                    print(f"  Error copying data: {e}")
                    session.rollback()
            else:
                rename_column_sqlite(session, 'fabrication_runs', 'operator', 'created_by')
        elif check_column_exists(session, 'fabrication_runs', 'created_by'):
            print("✓ fabrication_runs.created_by already exists (operator already renamed)")
        else:
            print("! Neither fabrication_runs.operator nor fabrication_runs.created_by exists, adding created_by")
            try:
                session.execute(text("ALTER TABLE fabrication_runs ADD COLUMN created_by VARCHAR(100)"))
                session.commit()
                print("✓ Added fabrication_runs.created_by column")
            except Exception as e:
                print(f"  Error adding column: {e}")
                session.rollback()
        
        # Analyses: operator -> created_by
        if check_column_exists(session, 'analyses', 'operator'):
            if check_column_exists(session, 'analyses', 'created_by'):
                print("! analyses.created_by already exists, copying data from operator")
                try:
                    session.execute(text("UPDATE analyses SET created_by = operator WHERE created_by IS NULL AND operator IS NOT NULL"))
                    session.commit()
                    print("✓ Copied analyses.operator data to created_by")
                except Exception as e:
                    print(f"  Error copying data: {e}")
                    session.rollback()
            else:
                rename_column_sqlite(session, 'analyses', 'operator', 'created_by')
        elif check_column_exists(session, 'analyses', 'created_by'):
            print("✓ analyses.created_by already exists (operator already renamed)")
        else:
            print("! Neither analyses.operator nor analyses.created_by exists, adding created_by")
            try:
                session.execute(text("ALTER TABLE analyses ADD COLUMN created_by VARCHAR(100)"))
                session.commit()
                print("✓ Added analyses.created_by column")
            except Exception as e:
                print(f"  Error adding column: {e}")
                session.rollback()
    
    print("\n=== Migration complete ===\n")


if __name__ == '__main__':
    migrate()
