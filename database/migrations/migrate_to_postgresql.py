"""
SQLite to PostgreSQL Migration Script
=====================================

Migrates data from a SQLite database to PostgreSQL.

Usage:
    python -m database.migrations.migrate_to_postgresql --postgres-url "postgresql://user:pass@localhost/pybirch"
    
    Or with environment variable:
    export DATABASE_URL="postgresql://user:pass@localhost/pybirch"
    python -m database.migrations.migrate_to_postgresql

Options:
    --sqlite-path: Path to SQLite database (default: database/pybirch.db)
    --postgres-url: PostgreSQL connection URL (or set DATABASE_URL env var)
    --dry-run: Show what would be migrated without actually doing it
    --skip-tables: Comma-separated list of tables to skip
"""

import os
import sys
import argparse
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.orm import sessionmaker
from database.models import Base


# Tables in dependency order (parents before children)
TABLE_ORDER = [
    'labs',
    'lab_members',
    'projects',
    'project_members',
    'users',
    'user_pins',
    'templates',
    'issues',
    'instruments',
    'equipment',
    'equipment_images',
    'equipment_issues',
    'precursors',
    'precursor_inventory',
    'procedures',
    'procedure_equipment',
    'procedure_precursors',
    'samples',
    'sample_precursors',
    'fabrication_runs',
    'queues',
    'queue_logs',
    'scans',
    'measurement_objects',
    'measurement_data_points',
    'measurement_data_arrays',
    'tags',
    'entity_tags',
]


def get_sqlite_tables(conn: sqlite3.Connection) -> List[str]:
    """Get list of tables in SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables


def get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    """Get column names for a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    cursor.close()
    return columns


def get_table_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Get row count for a table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_engine,
    table: str,
    batch_size: int = 1000,
    dry_run: bool = False
) -> int:
    """
    Migrate a single table from SQLite to PostgreSQL.
    
    Args:
        sqlite_conn: SQLite connection
        pg_engine: PostgreSQL SQLAlchemy engine
        table: Table name
        batch_size: Number of rows per batch
        dry_run: If True, don't actually insert data
        
    Returns:
        Number of rows migrated
    """
    columns = get_table_columns(sqlite_conn, table)
    if not columns:
        return 0
    
    total_rows = get_table_row_count(sqlite_conn, table)
    if total_rows == 0:
        return 0
    
    # Read all data from SQLite
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    
    migrated = 0
    
    if dry_run:
        print(f"  [DRY RUN] Would migrate {total_rows} rows from {table}")
        return total_rows
    
    # Build insert statement
    col_list = ', '.join(f'"{col}"' for col in columns)
    placeholders = ', '.join(f':{col}' for col in columns)
    insert_sql = text(f'INSERT INTO {table} ({col_list}) VALUES ({placeholders})')
    
    with pg_engine.connect() as pg_conn:
        batch = []
        
        for row in cursor:
            row_dict = dict(row)
            batch.append(row_dict)
            
            if len(batch) >= batch_size:
                pg_conn.execute(insert_sql, batch)
                pg_conn.commit()
                migrated += len(batch)
                print(f"    Migrated {migrated}/{total_rows} rows...", end='\r')
                batch = []
        
        # Insert remaining rows
        if batch:
            pg_conn.execute(insert_sql, batch)
            pg_conn.commit()
            migrated += len(batch)
    
    cursor.close()
    print(f"    Migrated {migrated}/{total_rows} rows.     ")
    return migrated


def reset_sequences(pg_engine, tables: List[str]):
    """Reset PostgreSQL sequences to max ID values after migration."""
    print("\nResetting sequences...")
    
    with pg_engine.connect() as conn:
        for table in tables:
            try:
                # Get max ID
                result = conn.execute(text(f"SELECT MAX(id) FROM {table}"))
                max_id = result.scalar()
                
                if max_id is not None:
                    # Reset sequence
                    seq_name = f"{table}_id_seq"
                    conn.execute(text(f"SELECT setval('{seq_name}', {max_id}, true)"))
                    conn.commit()
                    print(f"  Reset {seq_name} to {max_id}")
            except Exception as e:
                # Table might not have an id column or sequence
                pass


def migrate_database(
    sqlite_path: str,
    postgres_url: str,
    skip_tables: Optional[List[str]] = None,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Migrate entire database from SQLite to PostgreSQL.
    
    Args:
        sqlite_path: Path to SQLite database file
        postgres_url: PostgreSQL connection URL
        skip_tables: Tables to skip
        dry_run: If True, don't actually modify PostgreSQL
        
    Returns:
        Dictionary of table names to row counts migrated
    """
    skip_tables = skip_tables or []
    results = {}
    
    # Connect to SQLite
    print(f"Connecting to SQLite: {sqlite_path}")
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")
    
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_tables = get_sqlite_tables(sqlite_conn)
    
    print(f"Found {len(sqlite_tables)} tables in SQLite database")
    
    # Connect to PostgreSQL
    print(f"Connecting to PostgreSQL: {postgres_url.split('@')[1] if '@' in postgres_url else 'localhost'}")
    pg_engine = create_engine(postgres_url, echo=False)
    
    # Create tables in PostgreSQL
    if not dry_run:
        print("Creating tables in PostgreSQL...")
        Base.metadata.create_all(pg_engine)
    
    # Determine migration order
    tables_to_migrate = []
    for table in TABLE_ORDER:
        if table in sqlite_tables and table not in skip_tables:
            tables_to_migrate.append(table)
    
    # Add any tables not in predefined order
    for table in sqlite_tables:
        if table not in tables_to_migrate and table not in skip_tables:
            tables_to_migrate.append(table)
    
    print(f"\nMigrating {len(tables_to_migrate)} tables...")
    
    # Disable foreign key checks during migration
    if not dry_run:
        with pg_engine.connect() as conn:
            conn.execute(text("SET session_replication_role = 'replica'"))
            conn.commit()
    
    try:
        # Migrate each table
        for table in tables_to_migrate:
            print(f"\n  Migrating: {table}")
            try:
                count = migrate_table(sqlite_conn, pg_engine, table, dry_run=dry_run)
                results[table] = count
            except Exception as e:
                print(f"    ERROR: {e}")
                results[table] = -1
    finally:
        # Re-enable foreign key checks
        if not dry_run:
            with pg_engine.connect() as conn:
                conn.execute(text("SET session_replication_role = 'origin'"))
                conn.commit()
    
    # Reset sequences
    if not dry_run:
        reset_sequences(pg_engine, tables_to_migrate)
    
    sqlite_conn.close()
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Migrate PyBirch database from SQLite to PostgreSQL"
    )
    parser.add_argument(
        '--sqlite-path',
        default=None,
        help='Path to SQLite database (default: database/pybirch.db)'
    )
    parser.add_argument(
        '--postgres-url',
        default=None,
        help='PostgreSQL connection URL (or set DATABASE_URL env var)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without actually doing it'
    )
    parser.add_argument(
        '--skip-tables',
        default='',
        help='Comma-separated list of tables to skip'
    )
    
    args = parser.parse_args()
    
    # Determine SQLite path
    sqlite_path = args.sqlite_path
    if sqlite_path is None:
        db_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sqlite_path = os.path.join(db_folder, "pybirch.db")
    
    # Determine PostgreSQL URL
    postgres_url = args.postgres_url or os.environ.get('DATABASE_URL')
    if not postgres_url:
        print("ERROR: PostgreSQL URL required. Use --postgres-url or set DATABASE_URL")
        sys.exit(1)
    
    # Handle Heroku-style URLs
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
    
    skip_tables = [t.strip() for t in args.skip_tables.split(',') if t.strip()]
    
    print("=" * 60)
    print("PyBirch SQLite to PostgreSQL Migration")
    print("=" * 60)
    print(f"SQLite:     {sqlite_path}")
    print(f"PostgreSQL: {postgres_url.split('@')[1] if '@' in postgres_url else postgres_url}")
    print(f"Dry run:    {args.dry_run}")
    if skip_tables:
        print(f"Skipping:   {', '.join(skip_tables)}")
    print("=" * 60)
    
    if not args.dry_run:
        confirm = input("\nThis will migrate data to PostgreSQL. Continue? [y/N] ")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(0)
    
    start_time = datetime.now()
    
    try:
        results = migrate_database(
            sqlite_path=sqlite_path,
            postgres_url=postgres_url,
            skip_tables=skip_tables,
            dry_run=args.dry_run
        )
        
        elapsed = datetime.now() - start_time
        
        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        
        total_rows = 0
        errors = 0
        for table, count in results.items():
            if count >= 0:
                total_rows += count
                print(f"  {table}: {count} rows")
            else:
                errors += 1
                print(f"  {table}: ERROR")
        
        print("-" * 60)
        print(f"Total rows migrated: {total_rows}")
        print(f"Errors: {errors}")
        print(f"Time elapsed: {elapsed}")
        print("=" * 60)
        
        if errors > 0:
            sys.exit(1)
            
    except Exception as e:
        print(f"\nMigration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
