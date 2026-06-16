"""
Database Connection Manager for AutoAgentHire
Supports PostgreSQL (Supabase) and SQLite with automatic fallback.
"""

import os
import sys
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, NullPool
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import models
from backend.database.models_complete import Base

_SQLITE_FALLBACK = 'sqlite:///./data/autoagenthire.db'
_echo = os.getenv('DEBUG', 'False').lower() == 'true'


def _make_engine(url: str):
    """Create a SQLAlchemy engine for the given URL."""
    if url.startswith('sqlite'):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=_echo,
        )
    # Strip asyncpg prefix — we always use psycopg2 for sync connections
    sync_url = url.replace('postgresql+asyncpg://', 'postgresql://', 1)
    if 'supabase' in sync_url or any(c in sync_url for c in ['.supabase.co', '.pooler.supabase.com']):
        return create_engine(
            sync_url,
            poolclass=NullPool,
            pool_pre_ping=True,
            echo=_echo,
            connect_args={"connect_timeout": 10},
        )
    # Generic PostgreSQL (local / Docker)
    return create_engine(
        sync_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=_echo,
        connect_args={"connect_timeout": 10},
    )


def _resolve_engine():
    """
    Try each DATABASE_URL candidate in order and return the first engine
    that can actually reach the server.

    Priority:
      1. SYNC_DATABASE_URL  (explicit sync override)
      2. DATABASE_URL       (primary setting)
      3. SQLite fallback    (local development safety net)
    """
    candidates = []
    for key in ('SYNC_DATABASE_URL', 'DATABASE_URL'):
        val = os.getenv(key, '').strip()
        if val and val not in candidates:
            candidates.append(val)
    candidates.append(_SQLITE_FALLBACK)  # always have a last resort

    for url in candidates:
        try:
            eng = _make_engine(url)
            # Skip the blocking liveness check at import time to prevent deployment hang
            display = url.split('@')[-1] if '@' in url else url
            print("[DB] Configured for: " + display)
            return eng, url
        except Exception as exc:
            display = url.split('@')[-1] if '@' in url else url
            print("[DB] WARNING - Could not connect to " + display + ": " + str(exc).splitlines()[0])

    raise RuntimeError("No database backend is reachable. Check your .env and network.")


# Build the engine once at import time
engine, DATABASE_URL = _resolve_engine()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Column migrations — ADD COLUMN IF NOT EXISTS is idempotent on PostgreSQL.
# SQLite does not support IF NOT EXISTS on ALTER TABLE, so we catch and ignore errors there.
_COLUMN_MIGRATIONS = [
    # (table, column, definition)
    ("users", "phone",    "VARCHAR(50)"),
    ("users", "location", "VARCHAR(255)"),
]


def _run_migrations():
    """Apply any missing column additions to existing tables."""
    is_sqlite = DATABASE_URL.startswith("sqlite")
    with engine.connect() as conn:
        for table, column, definition in _COLUMN_MIGRATIONS:
            try:
                if is_sqlite:
                    # SQLite: check information_schema equivalent
                    result = conn.execute(text(f"PRAGMA table_info({table})"))
                    cols = [row[1] for row in result]
                    if column in cols:
                        continue
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                else:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"
                    ))
                conn.commit()
                print(f"[DB] Migration: added column {table}.{column}")
            except Exception as exc:
                conn.rollback()
                msg = str(exc).lower()
                # "already exists" or "duplicate column" — safe to ignore
                if "already exists" in msg or "duplicate column" in msg:
                    pass
                else:
                    print(f"[DB] Migration warning ({table}.{column}): {str(exc).splitlines()[0]}")


def init_db():
    """Initialize database tables — creates all tables if they don't exist."""
    try:
        Path('./data').mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(bind=engine)
        print("[DB] Tables created/verified successfully")
    except Exception as e:
        print("[DB] WARNING - Table initialization error: " + str(e))
        print("Continuing without database initialization...")

    # Always run column migrations so new columns are added to pre-existing tables
    try:
        _run_migrations()
    except Exception as e:
        print("[DB] WARNING - Migration error: " + str(e))


def drop_db():
    """Drop all database tables (use with caution!)"""
    Base.metadata.drop_all(bind=engine)
    print("[DB] All database tables dropped")


def get_db() -> Generator[Session, None, None]:
    """Get database session (dependency injection for FastAPI)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class DatabaseManager:
    """Database manager class for advanced operations"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def create_session(self) -> Session:
        """Create a new database session"""
        return self.SessionLocal()
    
    def init_tables(self):
        """Initialize all database tables"""
        init_db()
    
    def reset_database(self):
        """Reset database (drop and recreate all tables)"""
        drop_db()
        init_db()
    
    def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print("[DB] Health check failed: " + str(e))
            return False


# Global database manager instance
db_manager = DatabaseManager()


# SQLite specific optimizations
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Enable foreign keys and WAL mode for SQLite"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
