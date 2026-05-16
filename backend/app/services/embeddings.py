"""Embedding generation via Ollama.

Wraps `langchain_ollama.OllamaEmbeddings` so the rest of the application
treats embeddings as a plain async function `embed_texts(list[str])
-> list[list[float]]`.

Errors from the Ollama HTTP API are translated into `EmbeddingError` so
they surface to the client as a clean 502 instead of a cryptic traceback.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from langchain_ollama import OllamaEmbeddings

from app.core.config import get_settings
from app.core.exceptions import EmbeddingError

log = logging.getLogger(__name__)


def _build_embedder() -> OllamaEmbeddings:
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


_embedder: OllamaEmbeddings | None = None


def _get_embedder() -> OllamaEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = _build_embedder()
    return _embedder


async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []
    embedder = _get_embedder()
    try:
        # LangChain's Ollama embeddings are sync; run in a thread to keep
        # the event loop responsive while a batch is in flight.
        return await asyncio.to_thread(embedder.embed_documents, list(texts))
    except Exception as exc:
        log.exception("Embedding generation failed")
        raise EmbeddingError(details={"reason": str(exc)}) from exc


async def embed_query(text: str) -> list[float]:
    embedder = _get_embedder()
    try:
        return await asyncio.to_thread(embedder.embed_query, text)
    except Exception as exc:
        log.exception("Query embedding failed")
        raise EmbeddingError(details={"reason": str(exc)}) from exc
