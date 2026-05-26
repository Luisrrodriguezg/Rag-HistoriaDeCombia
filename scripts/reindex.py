"""Re-embed every chunk from the on-disk documents.

Run after switching the embedding model (e.g. nomic-embed-text -> bge-m3),
once the backend has booted with `RAG_RESET_VECTORS=1` and recreated an empty
`chunks` table at the new dimension.

Usage (inside the backend container):
    docker compose exec backend python scripts/reindex.py

Or locally with the same .env loaded:
    python scripts/reindex.py

Documents themselves are untouched — only the `chunks` table is repopulated
from the binaries already stored under DOCS_STORAGE_PATH.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import delete, select

# Allow running this script from the repo root (`python scripts/reindex.py`).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.core.db import SessionLocal  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.models import Chunk, Document  # noqa: E402
from app.repositories import document_repo  # noqa: E402
from app.services.chunker import chunk_text, extract_text  # noqa: E402
from app.services.embeddings import embed_texts  # noqa: E402

log = logging.getLogger("reindex")


async def reindex_document(session, doc: Document) -> int:
    path = Path(doc.storage_path)
    if not path.exists():
        log.warning("skip %s — file missing at %s", doc.filename, path)
        return 0

    data = path.read_bytes()
    text = extract_text(doc.filename, data)
    chunks = chunk_text(text)
    if not chunks:
        log.warning("skip %s — 0 chunks after extraction", doc.filename)
        return 0

    # Wipe any pre-existing chunks for this document so a partial re-run is
    # idempotent. In the normal flow the table was dropped at boot, but a user
    # might rerun this script after an aborted pass.
    await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))

    embeddings = await embed_texts(chunks)
    await document_repo.add_chunks(
        session,
        document_id=doc.id,
        chunks=list(zip(range(len(chunks)), chunks, embeddings, strict=True)),
    )
    await session.commit()
    log.info("reindexed %s (%d chunks)", doc.filename, len(chunks))
    return len(chunks)


async def main() -> None:
    configure_logging()
    async with SessionLocal() as session:
        docs = (await session.execute(select(Document))).scalars().all()
        if not docs:
            log.info("no documents in the database — nothing to reindex")
            return
        log.info("reindexing %d document(s)…", len(docs))
        total_chunks = 0
        for doc in docs:
            total_chunks += await reindex_document(session, doc)
        log.info("done — %d chunks across %d documents", total_chunks, len(docs))


if __name__ == "__main__":
    asyncio.run(main())
