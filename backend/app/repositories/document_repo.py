"""Repository functions for documents and their chunks."""

from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document


async def create_document(
    session: AsyncSession,
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    owner_id: str,
    storage_path: str,
) -> Document:
    doc = Document(
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        owner_id=owner_id,
        storage_path=storage_path,
    )
    session.add(doc)
    await session.flush()  # populate doc.id
    return doc


async def add_chunks(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    chunks: Sequence[tuple[int, str, list[float]]],
) -> int:
    """Bulk-insert (chunk_index, content, embedding) triples."""
    session.add_all(
        Chunk(
            document_id=document_id,
            chunk_index=idx,
            content=content,
            embedding=embedding,
        )
        for idx, content, embedding in chunks
    )
    await session.flush()
    return len(chunks)


async def list_documents(session: AsyncSession, owner_id: str) -> list[dict]:
    """Return each user-owned document with its chunk count."""
    stmt = (
        select(
            Document.id,
            Document.filename,
            Document.content_type,
            Document.size_bytes,
            Document.created_at,
            func.count(Chunk.id).label("chunk_count"),
        )
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .where(Document.owner_id == owner_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": str(row.id),
            "filename": row.filename,
            "content_type": row.content_type,
            "size_bytes": row.size_bytes,
            "created_at": row.created_at.isoformat(),
            "chunk_count": row.chunk_count,
        }
        for row in rows
    ]


async def get_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    owner_id: str,
) -> Document | None:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.owner_id == owner_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def delete_document(session: AsyncSession, document_id: uuid.UUID, owner_id: str) -> int:
    stmt = (
        delete(Document)
        .where(Document.id == document_id, Document.owner_id == owner_id)
        .returning(Document.id)
    )
    result = await session.execute(stmt)
    deleted = result.fetchall()
    return len(deleted)
