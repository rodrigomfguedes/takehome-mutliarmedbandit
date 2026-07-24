from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings


engine: AsyncEngine = create_async_engine(
    settings.database.url,
    echo=settings.database.echo,
)


@event.listens_for(engine.sync_engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: object,
    connection_record: object,
) -> None:
    """
    Enable foreign-key enforcement for every SQLite connection.

    SQLite supports foreign keys, but they are disabled by default.
    """
    del connection_record

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session to FastAPI routes.

    The session is committed explicitly inside the service or route that
    performs the write operation. If an error occurs, the transaction is
    rolled back before the session is closed.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise