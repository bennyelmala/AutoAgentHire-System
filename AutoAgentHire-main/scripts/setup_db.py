"""
Database setup script.
Initializes the PostgreSQL database and creates tables.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.config import settings
from backend.database.models_complete import Base


async def init_db():
    """
    Initialize the database.
    Creates all tables defined in models.
    """
    print("🔧 Initializing database...")
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True,
        future=True
    )
    
    # Create tables
    async with engine.begin() as conn:
        # Drop all tables (be careful in production!)
        # await conn.run_sync(Base.metadata.drop_all)
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database initialized successfully!")
    print(f"📊 Tables created: {', '.join(Base.metadata.tables.keys())}")
    
    await engine.dispose()


def init_db_sync():
    """
    Initialize the database synchronously.
    Useful for Alembic migrations.
    """
    print("🔧 Initializing database (sync)...")
    
    # Create sync engine
    sync_url = settings.SYNC_DATABASE_URL
    if not sync_url:
        raise ValueError("SYNC_DATABASE_URL is not configured")
    engine = create_engine(
        sync_url,
        echo=True
    )
    
    # Create tables
    Base.metadata.create_all(engine)
    
    print("✅ Database initialized successfully!")
    print(f"📊 Tables created: {', '.join(Base.metadata.tables.keys())}")
    
    engine.dispose()


if __name__ == "__main__":
    # Run async initialization
    asyncio.run(init_db())
