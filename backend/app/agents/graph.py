"""LangGraph compilation + public entry point.

Graph shape:

    START
       │
       ▼
    retrieve
       │
       ▼
    classify
       │  decide_route
       ├──── refuse_with_topics ────► END
       │
       └──── generate ──► END

`run_agent` and `run_agent_stream` are the only functions imported by route
handlers. The streaming variant emits `node_start` / `node_end` events around
every node so the frontend can render a live trace of the agent's progress.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any, AsyncIterator

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes import (
    classify_node,
    decide_route,
    generate_node,
    generate_node_stream,
    refuse_with_topics_node,
    retrieve_node,
)
from app.agents.state import AgentState

log = logging.getLogger(__name__)


# Human-readable labels for each node — shown verbatim in the frontend trace.
NODE_LABELS: dict[str, str] = {
    "retrieve": "Recuperando contexto",
    "classify": "Clasificando relevancia",
    "generate": "Generando respuesta",
    "refuse_with_topics": "Preparando sugerencias",
}


@lru_cache(maxsize=1)
def _compile_graph() -> Any:
    """Compile once and reuse.

    NOTE: `run_agent` currently invokes the nodes inline rather than driving
    the compiled graph, because `retrieve_node` needs an `AsyncSession`
    parameter that the LangGraph runner doesn't pass through. The compiled
    graph remains as the canonical definition of the agent's topology.
    """
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("classify", classify_node)
    graph.add_node("generate", generate_node)
    graph.add_node("refuse_with_topics", refuse_with_topics_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "classify")
    graph.add_conditional_edges(
        "classify",
        decide_route,
        {
            "generate": "generate",
            "refuse_with_topics": "refuse_with_topics",
        },
    )
    graph.add_edge("generate", END)
    graph.add_edge("refuse_with_topics", END)

    return graph.compile()


def _format_sources(relevant: list) -> list[dict]:
    return [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "filename": c.document_filename,
            "similarity": round(c.similarity, 4),
            "snippet": c.content[:240],
        }
        for c in relevant
    ]


async def run_agent(
    *,
    question: str,
    session: AsyncSession,
    history: list[dict] | None = None,
) -> dict:
    """Run the full RAG flow for a single question (non-streaming).

    Returns `{answer, grounded, sources}` ready to be serialised by FastAPI.
    `history` is a chronological list of `{"question", "answer"}` dicts used
    by classify and generate to resolve follow-up references; it does NOT
    affect retrieval.
    """
    started = time.monotonic()

    initial: AgentState = {"question": question, "history": history or []}
    state: AgentState = {**initial, **(await retrieve_node(initial, session=session))}
    state = {**state, **(await classify_node(state))}

    if decide_route(state) == "refuse_with_topics":
        state = {**state, **refuse_with_topics_node(state)}
    else:
        state = {**state, **(await generate_node(state))}

    grounded = bool(state.get("is_grounded"))
    log.info(
        "run_agent: completed in %.1fs is_relevant=%s",
        time.monotonic() - started,
        state.get("is_relevant"),
    )

    relevant = state.get("retrieved") or []
    return {
        "answer": state.get("generation", ""),
        "grounded": grounded,
        "sources": _format_sources(relevant) if grounded else [],
    }


async def run_agent_stream(
    *,
    question: str,
    session: AsyncSession,
    history: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """Streaming variant of `run_agent`.

    Yields events the SSE route serialises as `data: {json}\\n\\n` lines:

        {"type": "node_start", "node": "<name>", "label": "<es-label>"}
        {"type": "node_end",   "node": "<name>", "meta": {...}}
        {"type": "token",      "value": "<piece>"}
        {"type": "done",       "answer": "...", "grounded": bool, "sources": [...]}

    `node_start` fires just before a node begins; `node_end` fires when it
    completes, carrying small diagnostic metadata (kept/total chunks, classify
    verdict, etc.). The frontend uses these to render a live trace of the
    LangGraph flow alongside the streamed answer.
    """
    started = time.monotonic()
    state: AgentState = {"question": question, "history": history or []}

    # ── retrieve ──────────────────────────────────────────
    yield {"type": "node_start", "node": "retrieve", "label": NODE_LABELS["retrieve"]}
    state = {**state, **(await retrieve_node(state, session=session))}
    retrieved = state.get("retrieved") or []
    candidates = state.get("candidates") or []
    yield {
        "type": "node_end",
        "node": "retrieve",
        "meta": {
            "kept": len(retrieved),
            "candidates": len(candidates),
            "top_similarity": (
                round(max((c.similarity for c in candidates), default=0.0), 3)
            ),
        },
    }

    # ── classify ──────────────────────────────────────────
    yield {"type": "node_start", "node": "classify", "label": NODE_LABELS["classify"]}
    state = {**state, **(await classify_node(state))}
    yield {
        "type": "node_end",
        "node": "classify",
        "meta": {
            "is_relevant": bool(state.get("is_relevant")),
            "topics": state.get("suggested_topics") or [],
        },
    }

    # ── branch: generate or refuse ────────────────────────
    if decide_route(state) == "refuse_with_topics":
        yield {
            "type": "node_start",
            "node": "refuse_with_topics",
            "label": NODE_LABELS["refuse_with_topics"],
        }
        state = {**state, **refuse_with_topics_node(state)}
        text = state.get("generation", "")
        # Emit the assembled refusal as a single token event so the UI can
        # render it in the same bubble the streaming answer would have used.
        yield {"type": "token", "value": text}
        yield {"type": "node_end", "node": "refuse_with_topics", "meta": {}}
        yield {
            "type": "done",
            "answer": text,
            "grounded": False,
            "sources": [],
        }
        log.info(
            "run_agent_stream: refused with topics in %.1fs",
            time.monotonic() - started,
        )
        return

    # ── generate (streaming) ──────────────────────────────
    yield {"type": "node_start", "node": "generate", "label": NODE_LABELS["generate"]}
    buffer: list[str] = []
    async for piece in generate_node_stream(state):
        buffer.append(piece)
        yield {"type": "token", "value": piece}
    accumulated = "".join(buffer)
    state = {**state, "generation": accumulated, "is_grounded": True}
    yield {
        "type": "node_end",
        "node": "generate",
        "meta": {"chars": len(accumulated)},
    }

    yield {
        "type": "done",
        "answer": accumulated,
        "grounded": True,
        "sources": _format_sources(state.get("retrieved") or []),
    }
    log.info(
        "run_agent_stream: completed in %.1fs", time.monotonic() - started
    )
