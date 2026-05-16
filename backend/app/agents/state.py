"""LangGraph state schema."""

from __future__ import annotations

from typing import TypedDict

from app.repositories.chunk_repo import RetrievedChunk


class AgentState(TypedDict, total=False):
    # Input
    question: str

    # Retrieval
    retrieved: list[RetrievedChunk]
    relevant: list[RetrievedChunk]

    # Generation
    generation: str
    is_grounded: bool
    route: str  # "generate" | "refuse"
