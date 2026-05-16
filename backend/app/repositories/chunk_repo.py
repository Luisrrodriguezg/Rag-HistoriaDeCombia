"""Vector similarity search over the `chunks` table.

We compute cosine *distance* with pgvector's `<=>` operator and convert it to
similarity = `1 - distance`. The application-level threshold compares against
similarity directly to keep `core.config.RAG_SIMILARITY_THRESHOLD` intuitive
(higher = stricter).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_filename: str
    content: str
    similarity: float


async def similarity_search(
    session: AsyncSession,
    *,
    query_embedding: list[float],
    k: int,
    min_similarity: float,
) -> list[RetrievedChunk]:
    """Return the top-`k` chunks above `min_similarity`."""
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(
            Chunk.id,
            Chunk.content,
            Document.id.label("document_id"),
            Document.filename,
            distance,
        )
        .join(Document, Document.id == Chunk.document_id)
        .order_by(distance.asc())
        .limit(k)
    )
    rows = (await session.execute(stmt)).all()

    out: list[RetrievedChunk] = []
    for row in rows:
        similarity = 1.0 - float(row.distance)
        if similarity < min_similarity:
            continue
        out.append(
            RetrievedChunk(
                chunk_id=str(row.id),
                document_id=str(row.document_id),
                document_filename=row.filename,
                content=row.content,
                similarity=similarity,
            )
        )
    return out
