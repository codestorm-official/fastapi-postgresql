import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 -- register models on Base.metadata
from app.database import Base, get_db
from app.main import app
from app.redis_client import get_redis


@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite shared across connections via StaticPool."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_redis():
    cache = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield cache
    await cache.aclose()


@pytest_asyncio.fixture
async def client(db_engine, fake_redis):
    """HTTP client with get_db / get_redis overridden to test doubles."""
    TestSession = async_sessionmaker(
        db_engine, expire_on_commit=False, class_=AsyncSession
    )

    async def override_get_db():
        async with TestSession() as session:
            yield session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
