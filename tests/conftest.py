"""Test fixtures — uses an in-memory SQLite database for speed.

The production app targets PostgreSQL via async SQLAlchemy. SQLite is a
practical substitute for unit tests because we don't exercise any PG-specific
features (the UUID column type works under SQLite via the SQLAlchemy generic
backend).
"""
import os
from typing import AsyncGenerator

# Provide minimal env vars before importing the app.
os.environ.setdefault("SECRET_KEY", "test-secret-key-very-long-string-for-jwt-signing-x")
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///:memory:"
)
os.environ.setdefault("FERNET_KEY", "beVifUSMFl6iQMreRKCPa14av-GkWAzB5hWRO-iehy4=")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "TestAdminPassword!")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.database as database_module
from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
