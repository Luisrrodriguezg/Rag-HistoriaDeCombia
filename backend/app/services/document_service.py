"""Document ingestion pipeline.

Orchestrates: receive bytes → persist to disk → extract text → chunk →
embed → upsert to pgvector. Embedding generation is a separate service
(`services.embeddings`) so it can be swapped without touching this module.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DocumentNotFound
from app.repositories import document_repo
from app.services.chunker import chunk_text, extract_text
from app.services.embeddings import embed_texts

log = logging.getLogger(__name__)


async def ingest_document(
    session: AsyncSession,
    *,
    owner_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> dict:
    settings = get_settings()
    storage_dir = Path(settings.docs_storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)

    doc_uuid = uuid.uuid4()
    storage_path = storage_dir / f"{doc_uuid}{Path(filename).suffix.lower()}"
    storage_path.write_bytes(data)

    # Extract + chunk before touching the DB so a corrupted file fails fast.
    text = extract_text(filename, data)
    chunks = chunk_text(text)
    if not chunks:
        log.warning("Document %s produced 0 chunks after extraction", filename)

    document = await document_repo.create_document(
        session,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        owner_id=owner_id,
        storage_path=str(storage_path),
    )

    if chunks:
        embeddings = await embed_texts(chunks)
        await document_repo.add_chunks(
            session,
            document_id=document.id,
            chunks=list(zip(range(len(chunks)), chunks, embeddings, strict=True)),
        )

    await session.commit()
    log.info(
        "Ingested document filename=%s chunks=%d owner=%s",
        filename,
        len(chunks),
        owner_id,
    )
    return {
        "id": str(document.id),
        "filename": filename,
        "chunk_count": len(chunks),
    }


async def delete_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    owner_id: str,
) -> None:
    deleted = await document_repo.delete_document(session, document_id, owner_id)
    if deleted == 0:
        raise DocumentNotFound(details={"id": str(document_id)})
    await session.commit()

    # Best-effort cleanup of the binary; missing file is non-fatal.
    settings = get_settings()
    for f in Path(settings.docs_storage_path).glob(f"{document_id}*"):
        try:
            f.unlink()
        except OSError as exc:
            log.warning("Could not delete storage file %s: %s", f, exc)
