from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import src.models
from src.core.database import get_database_session
from src.main import app
from src.models import Base


# Keep the test database fully isolated from the local application database.
# StaticPool is important here because an in-memory SQLite database only exists
# for the lifetime of a connection, so all test sessions must share one.
TEST_DATABASE_URL = "sqlite+aiosqlite://"


test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def enable_sqlite_foreign_keys(
    dbapi_connection: object,
    connection_record: object,
) -> None:
    # SQLite does not enforce foreign keys unless this pragma is enabled for
    # each connection. Mirroring production behavior prevents tests from
    # passing with relationships that would fail in the real application.
    del connection_record

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def override_database_session() -> AsyncGenerator[
    AsyncSession,
    None,
]:
    # FastAPI will use this session dependency during integration tests instead
    # of the application's regular SQLite session.
    async with test_session_factory() as session:
        try:
            yield session
        except Exception:
            # Roll back failed requests so one test cannot leave an open or
            # partially applied transaction behind for the next request.
            await session.rollback()
            raise


@pytest_asyncio.fixture(autouse=True)
async def reset_database() -> AsyncGenerator[None, None]:
    # Recreate the schema for every test. This is slightly more work than
    # truncating tables, but it gives each test a predictable clean state and
    # also validates that the SQLAlchemy metadata can build the full schema.
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    yield

    # Drop everything again after the test so failures do not leak state into
    # later tests or make their outcome depend on execution order.
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # Dependency overrides let the tests exercise the real FastAPI routes while
    # keeping all database access inside the isolated in-memory database.
    app.dependency_overrides[
        get_database_session
    ] = override_database_session

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as test_client:
        yield test_client

    # Clear overrides after every test to avoid contaminating other test
    # modules or any code that imports the application in the same process.
    app.dependency_overrides.clear()