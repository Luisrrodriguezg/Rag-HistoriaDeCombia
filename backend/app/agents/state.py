"""LangGraph state schema."""

from __future__ import annotations

from typing import TypedDict

from app.repositories.chunk_repo import RetrievedChunk


class AgentState(TypedDict, total=False):
    # Input
    question: str
    # Prior conversation turns (chronological, oldest first) used by classify
    # and generate to resolve follow-up references like "él", "ese", "y...".
    # Each item is {"question": str, "answer": str}. Retrieval ignores this.
    history: list[dict]

    # Retrieval
    # `candidates`: every top-k chunk regardless of similarity threshold,
    # available to the refuse path so it can still surface "topics we DO have"
    # even when nothing scored above the threshold.
    # `retrieved`: chunks above the similarity threshold — what classify_node
    # actually evaluates and what generate_node uses as context.
    candidates: list[RetrievedChunk]
    retrieved: list[RetrievedChunk]

    # Classification
    is_relevant: bool
    suggested_topics: list[str]

    # Generation
    generation: str
    is_grounded: bool
    route: str  # "generate" | "refuse_with_topics"
