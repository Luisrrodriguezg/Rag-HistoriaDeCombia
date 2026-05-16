"""Text extraction + chunking.

Extraction supports the formats listed in the project rubric: PDF, TXT, MD,
DOCX. Anything else raises `UnsupportedFileType`, which the handler in
`core/exceptions` turns into a clean 415 response.

Chunking uses LangChain's `RecursiveCharacterTextSplitter` with project-tuned
defaults (size / overlap come from settings so they can be tweaked without a
redeploy).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.exceptions import DocumentProcessingError, UnsupportedFileType

log = logging.getLogger(__name__)

# (extension, content_type substring) → extractor name.
_SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown", ".docx"}


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # pypdf raises a zoo of exception types
        raise DocumentProcessingError(
            "Failed to extract text from PDF.",
            details={"reason": str(exc)},
        ) from exc


def _extract_docx(data: bytes) -> str:
    try:
        doc = DocxDocument(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        raise DocumentProcessingError(
            "Failed to extract text from DOCX.",
            details={"reason": str(exc)},
        ) from exc


def _extract_text(data: bytes) -> str:
    # Best-effort decoding: try utf-8, fall back to latin-1.
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def extract_text(filename: str, data: bytes) -> str:
    """Return the plain-text content of an uploaded file."""
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise UnsupportedFileType(
            f"File extension '{suffix}' is not supported.",
            details={
                "filename": filename,
                "supported": sorted(_SUPPORTED_SUFFIXES),
            },
        )

    if suffix == ".pdf":
        return _extract_pdf(data)
    if suffix == ".docx":
        return _extract_docx(data)
    return _extract_text(data)  # .txt, .md, .markdown


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks suitable for embedding."""
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = [c.strip() for c in splitter.split_text(text)]
    return [c for c in chunks if c]
