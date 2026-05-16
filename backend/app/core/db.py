"""Database engine, session factory and one-shot schema bootstrap.

Why no Alembic: scope of this project is a one-shot graded delivery. The
container's `db/init.sql` (mounted into `/docker-entrypoint-initdb.d/`) takes
care of `CREATE EXTENSION vector`. Everything else is created by SQLAlchemy
`Base.metadata.create_all` during the FastAPI `lifespan`. An `ivfflat` cosine
index on `chunks.embedding` is added with raw SQL because SQLAlchemy core does
not model pgvector indexes natively.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models import Base

log = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create tables and the pgvector index if they don't exist.

    Invoked from the FastAPI lifespan exactly once on startup.
    """
    async with engine.begin() as conn:
        # The extension itself is enabled by db/init.sql; this is a safety net
        # for environments that bypass docker-entrypoint-initdb.d (e.g. tests).
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        # ivfflat index for cosine similarity searches. 100 lists is a safe
        # default for ~10k-100k vectors; revisit if the corpus grows.
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chunks_embedding_cosine_idx "
                "ON chunks USING ivfflat (embedding vector_cosine_ops) "
                "WITH (lists = 100)"
            )
        )
    log.info("Database schema initialised (tables + ivfflat index ensured)")


async def get_session() -> AsyncSession:
    """Async dependency for FastAPI routes — yields a session, closes on exit."""
    async with SessionLocal() as session:
        yield session
