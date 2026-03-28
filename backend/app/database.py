from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    echo=settings.environment == "development",
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yields an async DB session."""
    async with SessionLocal() as session:
        yield session


async def get_raw_connection() -> AsyncGenerator[AsyncConnection, None]:
    """Dependency: yields a raw async connection for bulk writes."""
    async with engine.connect() as conn:
        yield conn
        await conn.commit()
