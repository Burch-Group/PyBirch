"""
PyBirch Database Session Management
===================================
Database connection, session management, and initialization utilities.

Supports both SQLite (default for local development) and PostgreSQL (recommended for production).

Configuration:
    Set the DATABASE_URL environment variable to use PostgreSQL:
    
        export DATABASE_URL="postgresql://user:password@localhost:5432/pybirch"
    
    Or pass the URL directly to DatabaseManager or init_db().
"""

import os
from typing import Optional, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import StaticPool, QueuePool

from database.models import Base


def get_database_url() -> str:
    """
    Get database URL from environment or use default SQLite.
    
    Checks DATABASE_URL environment variable first, then falls back to SQLite.
    
    Returns:
        Database connection URL string
    """
    env_url = os.environ.get('DATABASE_URL')
    if env_url:
        # Handle Heroku-style postgres:// URLs
        if env_url.startswith('postgres://'):
            env_url = env_url.replace('postgres://', 'postgresql://', 1)
        return env_url
    
    # Default to SQLite in the database folder
    db_folder = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_folder, "pybirch.db")
    return f"sqlite:///{db_path}"


class DatabaseManager:
    """
    Manages database connections and sessions for PyBirch.
    
    Supports both SQLite (default for local development) and PostgreSQL.
    
    Usage:
        # Initialize with default SQLite database
        db = DatabaseManager()
        
        # Or with a specific database URL
        db = DatabaseManager("postgresql://user:pass@localhost/pybirch")
        
        # Get a session
        with db.session() as session:
            samples = session.query(Sample).all()
    """
    
    _instance: Optional['DatabaseManager'] = None
    
    def __init__(
        self, 
        database_url: Optional[str] = None,
        echo: bool = False,
        create_tables: bool = True
    ):
        """
        Initialize the database manager.
        
        Args:
            database_url: Database connection URL. If None, checks DATABASE_URL env var,
                         then falls back to SQLite in the database folder.
            echo: If True, SQLAlchemy will log all SQL statements.
            create_tables: If True, creates all tables on initialization.
        """
        if database_url is None:
            database_url = get_database_url()
        
        self.database_url = database_url
        self._echo = echo
        self._is_sqlite = database_url.startswith("sqlite")
        self._is_postgresql = database_url.startswith("postgresql")
        
        # Create engine with appropriate settings
        if self._is_sqlite:
            # SQLite-specific settings for better concurrency
            self._engine = create_engine(
                database_url,
                echo=echo,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool if ":memory:" in database_url else None
            )
            # Enable foreign keys and WAL mode for better concurrency
            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent access
                cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes with reasonable safety
                cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
                cursor.execute("PRAGMA busy_timeout=5000")  # 5 second timeout on locks
                cursor.close()
        else:
            # PostgreSQL or other databases - optimized for concurrent access
            self._engine = create_engine(
                database_url,
                echo=echo,
                poolclass=QueuePool,
                pool_size=10,  # Base connections
                max_overflow=20,  # Extra connections under load
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,  # Recycle connections after 1 hour
                connect_args={
                    "connect_timeout": 10,
                    "application_name": "PyBirch",
                } if self._is_postgresql else {}
            )
        
        # Create session factory
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False
        )
        
        # Create scoped session for thread-safe access
        self._scoped_session = scoped_session(self._session_factory)
        
        # Create tables if requested
        if create_tables:
            self.create_all()
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'DatabaseManager':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing)."""
        if cls._instance is not None:
            cls._instance.dispose()
            cls._instance = None
    
    @property
    def engine(self):
        """Get the SQLAlchemy engine."""
        return self._engine
    
    def create_all(self):
        """Create all database tables."""
        Base.metadata.create_all(self._engine)
    
    def drop_all(self):
        """Drop all database tables. Use with caution!"""
        Base.metadata.drop_all(self._engine)
    
    def dispose(self):
        """Dispose of the connection pool."""
        self._scoped_session.remove()
        self._engine.dispose()
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.
        
        Usage:
            with db.session() as session:
                sample = Sample(sample_id="S001", material="Gold")
                session.add(sample)
                # Automatically commits on success, rolls back on error
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session(self) -> Session:
        """
        Get a new session. Caller is responsible for commit/rollback/close.
        
        For most use cases, prefer using the session() context manager.
        """
        return self._session_factory()
    
    def get_scoped_session(self) -> Session:
        """
        Get a thread-local scoped session.
        
        Useful for web frameworks or multi-threaded applications.
        """
        return self._scoped_session()
    
    def remove_scoped_session(self):
        """Remove the current scoped session."""
        self._scoped_session.remove()
    
    def execute_raw(self, sql: str, params: Optional[dict] = None):
        """
        Execute raw SQL statement.
        
        Args:
            sql: SQL statement to execute.
            params: Optional parameters for the statement.
            
        Returns:
            Result proxy from execution.
        """
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            conn.commit()
            return result
    
    def health_check(self) -> bool:
        """
        Check if the database connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    def get_table_stats(self) -> dict:
        """
        Get statistics about database tables.
        
        Returns:
            Dictionary with table names and row counts.
        """
        stats = {}
        with self.session() as session:
            for table in Base.metadata.tables.keys():
                try:
                    count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    stats[table] = count
                except Exception:
                    stats[table] = -1  # Error counting
        return stats


# Global database instance (lazy initialization)
_db_manager: Optional[DatabaseManager] = None


def init_db(
    database_url: Optional[str] = None,
    echo: bool = False,
    create_tables: bool = True
) -> DatabaseManager:
    """
    Initialize the global database manager.
    
    Args:
        database_url: Database connection URL. If None, uses SQLite in the database folder.
        echo: If True, SQLAlchemy will log all SQL statements.
        create_tables: If True, creates all tables on initialization.
        
    Returns:
        The DatabaseManager instance.
    """
    global _db_manager
    if _db_manager is not None:
        _db_manager.dispose()
    _db_manager = DatabaseManager(
        database_url=database_url,
        echo=echo,
        create_tables=create_tables
    )
    return _db_manager


def get_db() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Initializes with default settings if not already initialized.
    
    Returns:
        The DatabaseManager instance.
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Convenience function to get a database session.
    
    Usage:
        with get_session() as session:
            samples = session.query(Sample).all()
    """
    db = get_db()
    with db.session() as session:
        yield session


def close_db():
    """Close the global database connection."""
    global _db_manager
    if _db_manager is not None:
        _db_manager.dispose()
        _db_manager = None
