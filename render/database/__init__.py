"""Database initialization and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from .models import Base

# Create async engine for metadata database
engine = create_async_engine(
    settings.meta_db_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()


__all__ = ["AsyncSessionLocal", "init_db", "close_db", "Base"]
