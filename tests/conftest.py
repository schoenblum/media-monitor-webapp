"""Test fixtures — uses a per-session SQLite file so multiple aiosqlite connections
see the same schema (an in-memory ``:memory:`` URL gives each connection its
own private database, which breaks the bootstrap → request flow).

The production app targets PostgreSQL via async SQLAlchemy. SQLite is a
practical substitute for unit tests because we don't exercise any PG-specific
features (the UUID column type works under SQLite via the SQLAlchemy generic
backend).
"""
import os
import tempfile
import uuid

# Use a unique SQLite file per test session so suites cannot interfere.
_DB_FILE = os.path.join(tempfile.gettempdir(), f"mm-test-{uuid.uuid4().hex}.sqlite")

# Force test-suite env vars BEFORE importing the app so pydantic-settings picks
# them up. These override any `.env` that may live in the working directory.
os.environ["SECRET_KEY"] = "test-secret-key-very-long-string-for-jwt-signing-x"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_FILE}"
os.environ["FERNET_KEY"] = "beVifUSMFl6iQMreRKCPa14av-GkWAzB5hWRO-iehy4="
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "TestAdminPassword!"

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.database as database_module
from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def engine():
    # Reset the database file at the start of every test for isolation.
    if os.path.exists(_DB_FILE):
        os.remove(_DB_FILE)
    eng = create_async_engine(os.environ["DATABASE_URL"], future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(engine, session_factory) -> AsyncGenerator[AsyncClient, None]:
    # Wire the app to use our test session factory for both dependency-injected
    # sessions and the background-task SessionLocal.
    database_module.SessionLocal = session_factory  # type: ignore[assignment]

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # The default ASGITransport does not invoke FastAPI lifespan events, so we
    # call bootstrap_admin explicitly to seed the admin account + default outlets.
    from app.bootstrap import bootstrap_admin

    await bootstrap_admin()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
