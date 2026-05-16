"""Pydantic v2 schemas for the documents API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int = 0
    created_at: datetime


class DocumentCreated(BaseModel):
    id: str
    filename: str
    chunk_count: int = Field(description="Number of text chunks indexed for this document.")
