"""Async SQLAlchemy database lifecycle and transaction boundaries."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Own the async engine and yield one session per operation."""

    def __init__(self, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a request/job-scoped session without committing implicitly."""
        async with self._session_factory() as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Yield a session whose operation commits on success and rolls back on failure."""
        async with self._session_factory() as session:
            async with session.begin():
                yield session

    async def dispose(self) -> None:
        """Release pooled database connections during application shutdown."""
        await self._engine.dispose()
