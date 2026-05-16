"""LangGraph nodes — pure functions of `AgentState`.

Each node returns a *partial* state update; LangGraph merges it with the
current state. This keeps node bodies tiny and trivially testable.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_ollama import ChatOllama
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (
    ANSWER_PROMPT,
    GRADE_DOC_PROMPT,
    GROUNDING_PROMPT,
    REFUSAL_MESSAGE,
)
from app.agents.state import AgentState
from app.core.config import get_settings
from app.core.exceptions import LLMUnavailable
from app.repositories import chunk_repo
from app.services.embeddings import embed_query

log = logging.getLogger(__name__)


_chat: ChatOllama | None = None


def _get_chat() -> ChatOllama:
    """Lazy-init the Ollama chat client so unit tests can patch it cleanly."""
    global _chat
    if _chat is None:
        settings = get_settings()
        _chat = ChatOllama(
            model=settings.ollama_llm_model,
            base_url=settings.ollama_base_url,
            temperature=0.0,
        )
    return _chat


async def _llm_invoke(prompt: str) -> str:
    chat = _get_chat()
    try:
        msg = await asyncio.to_thread(chat.invoke, prompt)
    except Exception as exc:
        log.exception("LLM invocation failed")
        raise LLMUnavailable(details={"reason": str(exc)}) from exc
    content = getattr(msg, "content", str(msg))
    return content.strip()


# ──────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────


async def retrieve_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    """Embed the question and pull the top-k similar chunks above threshold."""
    settings = get_settings()
    question = state["question"]
    embedding = await embed_query(question)
    chunks = await chunk_repo.similarity_search(
        session,
        query_embedding=embedding,
        k=settings.rag_top_k,
        min_similarity=settings.rag_similarity_threshold,
    )
    log.info(
        "retrieve: question='%s…' candidates_above_threshold=%d",
        question[:60],
        len(chunks),
    )
    return {"retrieved": chunks}


async def grade_documents_node(state: AgentState) -> AgentState:
    """LLM-based relevance filter on top of similarity ranking.

    This is a second line of defence: pgvector already returned high-similarity
    chunks, but lexical overlap can still mislead. The LLM here is asked a
    very simple yes/no question to keep latency low.
    """
    retrieved = state.get("retrieved") or []
    if not retrieved:
        return {"relevant": []}

    relevant: list = []
    for chunk in retrieved:
        verdict = await _llm_invoke(
            GRADE_DOC_PROMPT.format(question=state["question"], document=chunk.content)
        )
        if verdict.strip().lower().startswith("y"):
            relevant.append(chunk)
    log.info("grade_documents: kept=%d/%d", len(relevant), len(retrieved))
    return {"relevant": relevant}


def decide_route(state: AgentState) -> str:
    """Conditional edge selector."""
    relevant = state.get("relevant") or []
    return "generate" if relevant else "refuse"


async def generate_node(state: AgentState) -> AgentState:
    """Prompt the LLM to answer using ONLY the relevant context."""
    relevant = state.get("relevant") or []
    context = "\n\n---\n\n".join(
        f"[{i + 1}] {c.content}" for i, c in enumerate(relevant)
    )
    answer = await _llm_invoke(
        ANSWER_PROMPT.format(
            refusal=REFUSAL_MESSAGE,
            context=context,
            question=state["question"],
        )
    )
    return {"generation": answer}


async def grade_generation_node(state: AgentState) -> AgentState:
    """Final hallucination check — verify the answer is grounded in context."""
    relevant = state.get("relevant") or []
    generation = state.get("generation", "")

    # If the model already self-refused, accept it without another LLM call.
    if REFUSAL_MESSAGE.strip()[:60] in generation:
        return {"is_grounded": False, "generation": REFUSAL_MESSAGE}

    context = "\n\n---\n\n".join(c.content for c in relevant)
    verdict = await _llm_invoke(
        GROUNDING_PROMPT.format(context=context, answer=generation)
    )
    grounded = verdict.strip().lower().startswith("y")
    log.info("grade_generation: grounded=%s", grounded)
    if not grounded:
        return {"is_grounded": False, "generation": REFUSAL_MESSAGE}
    return {"is_grounded": True}


def refuse_node(_: AgentState) -> AgentState:
    """Terminal node when there is no relevant context."""
    return {"generation": REFUSAL_MESSAGE, "is_grounded": False}
