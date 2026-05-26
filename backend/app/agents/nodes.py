"""LangGraph nodes — pure functions of `AgentState`.

Each node returns a *partial* state update; LangGraph merges it with the
current state. This keeps node bodies tiny and trivially testable.

Flow:
    retrieve → classify → (is_relevant ? generate : refuse_with_topics) → END

Compared to the earlier 3-LLM-call design, we collapsed `grade_documents`
(per-chunk yes/no) and `grade_generation` (post-hoc grounding check) into a
single `classify` call that ALSO surfaces "topics we DO have" for the refusal
path. This makes conversational queries like "háblame de Colombia" work,
because relevance is judged holistically over the retrieved set rather than
per-chunk.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from langchain_ollama import ChatOllama
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (
    ANSWER_PROMPT,
    CLASSIFY_PROMPT,
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
            num_ctx=settings.ollama_num_ctx,
            keep_alive=settings.ollama_keep_alive,
        )
    return _chat


async def _llm_invoke(prompt: str) -> str:
    chat = _get_chat()
    try:
        msg = await chat.ainvoke(prompt)
    except Exception as exc:
        log.exception("LLM invocation failed")
        raise LLMUnavailable(details={"reason": str(exc)}) from exc
    content = getattr(msg, "content", str(msg))
    return content.strip()


async def _llm_stream(prompt: str) -> AsyncIterator[str]:
    """Yield text chunks as the model produces them."""
    chat = _get_chat()
    try:
        async for chunk in chat.astream(prompt):
            piece = getattr(chunk, "content", "") or ""
            if piece:
                yield piece
    except Exception as exc:
        log.exception("LLM streaming failed")
        raise LLMUnavailable(details={"reason": str(exc)}) from exc


def _format_history(history: list[dict] | None) -> str:
    """Render prior turns as a labelled block, or empty string if none.

    Empty string keeps the prompt clean when there is no history — no awkward
    "Conversación previa: (ninguna)" header. When present, the block ends with
    a trailing blank line so it sits cleanly above the next prompt section.
    """
    if not history:
        return ""
    lines: list[str] = ["Conversación previa (orden cronológico, la pregunta actual viene después):"]
    for i, turn in enumerate(history, start=1):
        q = (turn.get("question") or "").strip()
        a = (turn.get("answer") or "").strip()
        # Trim very long prior answers so a long thread doesn't blow up the
        # prompt — first 400 chars is enough to recover pronoun antecedents.
        if len(a) > 400:
            a = a[:400].rstrip() + "…"
        lines.append(f"[{i}] Usuario: {q}\n    Asistente: {a}")
    return "\n".join(lines) + "\n\n"


# ──────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────


async def retrieve_node(state: AgentState, *, session: AsyncSession) -> AgentState:
    """Embed the question and pull the top-k similar chunks.

    Returns BOTH the full candidate list (`candidates`, unfiltered) and the
    above-threshold subset (`retrieved`). The refuse path uses `candidates`
    to surface "topics we DO have" even when nothing crossed the threshold.
    """
    settings = get_settings()
    question = state["question"]
    embedding = await embed_query(question)
    candidates = await chunk_repo.similarity_search(
        session,
        query_embedding=embedding,
        k=settings.rag_top_k,
    )
    log.info(
        "retrieve: q='%s' top-%d similarities=%s",
        question[:60],
        settings.rag_top_k,
        [f"{c.similarity:.3f}|{c.document_filename}" for c in candidates],
    )
    kept = [c for c in candidates if c.similarity >= settings.rag_similarity_threshold]
    log.info(
        "retrieve: kept %d/%d above threshold=%.2f",
        len(kept),
        len(candidates),
        settings.rag_similarity_threshold,
    )
    return {"candidates": candidates, "retrieved": kept}


def _parse_classify_verdict(text: str) -> tuple[bool, list[str]]:
    """Parse the classify LLM output into (is_relevant, suggested_topics).

    Accepted forms (case-insensitive, first non-empty line):
        YES
        NO: tema 1; tema 2; tema 3

    Tolerant of leading/trailing whitespace and trailing punctuation.
    Anything that doesn't start with NO is treated as YES (bias toward
    answering — the prompt itself tells the model to be generous).
    """
    line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    lower = line.lower()
    if lower.startswith("no"):
        _, _, rest = line.partition(":")
        topics = [t.strip(" .;-").strip() for t in rest.split(";")]
        topics = [t for t in topics if t]
        return False, topics[:4]
    return True, []


async def classify_node(state: AgentState) -> AgentState:
    """Single LLM call: is the retrieved context relevant to the question?

    When the verdict is NO, the same call extracts a short list of topics
    from the context so the refusal can suggest what the user could ask
    instead.

    Edge case: when `retrieved` is empty (nothing above the similarity
    threshold), we skip the LLM call entirely — the answer is trivially "no"
    — and surface topics from the broader candidate set if any exist.
    """
    retrieved = state.get("retrieved") or []
    candidates = state.get("candidates") or []

    if not retrieved:
        # Below-threshold candidates can still hint at topics in the corpus.
        topics = _topics_from_filenames(candidates)
        log.info(
            "classify: no chunks above threshold — skipping LLM. "
            "fallback topics from filenames: %s",
            topics,
        )
        return {"is_relevant": False, "suggested_topics": topics}

    context = "\n\n---\n\n".join(
        f"[{i + 1}] {c.content}" for i, c in enumerate(retrieved)
    )
    verdict_text = await _llm_invoke(
        CLASSIFY_PROMPT.format(
            history=_format_history(state.get("history")),
            question=state["question"],
            context=context,
        )
    )
    is_relevant, topics = _parse_classify_verdict(verdict_text)
    log.info(
        "classify: verdict=%r -> is_relevant=%s topics=%s",
        verdict_text[:80],
        is_relevant,
        topics,
    )
    return {"is_relevant": is_relevant, "suggested_topics": topics}


def _topics_from_filenames(chunks: list) -> list[str]:
    """Last-ditch topic fallback: unique source filenames, stripped of ext."""
    seen: list[str] = []
    for c in chunks:
        name = c.document_filename.rsplit(".", 1)[0]
        if name not in seen:
            seen.append(name)
        if len(seen) >= 4:
            break
    return seen


def decide_route(state: AgentState) -> str:
    """Conditional edge selector — picks between generate and refuse paths."""
    return "generate" if state.get("is_relevant") else "refuse_with_topics"


async def generate_node(state: AgentState) -> AgentState:
    """Prompt the LLM to answer using the retrieved context (non-streaming)."""
    relevant = state.get("retrieved") or []
    context = "\n\n---\n\n".join(
        f"[{i + 1}] {c.content}" for i, c in enumerate(relevant)
    )
    answer = await _llm_invoke(
        ANSWER_PROMPT.format(
            refusal=REFUSAL_MESSAGE,
            history=_format_history(state.get("history")),
            context=context,
            question=state["question"],
        )
    )
    log.info("generate: answer[:120]=%r", answer[:120])
    return {"generation": answer, "is_grounded": True}


async def generate_node_stream(state: AgentState) -> AsyncIterator[str]:
    """Streaming counterpart of `generate_node`."""
    relevant = state.get("retrieved") or []
    context = "\n\n---\n\n".join(
        f"[{i + 1}] {c.content}" for i, c in enumerate(relevant)
    )
    prompt = ANSWER_PROMPT.format(
        refusal=REFUSAL_MESSAGE,
        history=_format_history(state.get("history")),
        context=context,
        question=state["question"],
    )
    async for piece in _llm_stream(prompt):
        yield piece


def refuse_with_topics_node(state: AgentState) -> AgentState:
    """Compose the refusal message and append topic suggestions if any."""
    topics = state.get("suggested_topics") or []
    if topics:
        topics_str = ", ".join(topics)
        text = (
            f"{REFUSAL_MESSAGE} Sin embargo, en mi base de conocimiento sí tengo "
            f"información sobre: {topics_str}. ¿Quieres preguntar algo sobre alguno de estos?"
        )
    else:
        text = REFUSAL_MESSAGE
    return {"generation": text, "is_grounded": False}
