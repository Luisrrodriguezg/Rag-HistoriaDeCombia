"""Pydantic schemas for the /chat endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


class Source(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    similarity: float
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    sources: list[Source]


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    answer: str
    grounded: bool
    sources: list[dict]
    created_at: datetime
