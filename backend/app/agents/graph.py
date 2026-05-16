"""LangGraph compilation + public entry point.

Graph shape:

    START
       │
       ▼
    retrieve
       │
       ▼
    grade_documents
       │  decide_route
       ├──── refuse ────► END
       │
       └──── generate ──► grade_generation ──► END

`run_agent` is the only function imported by route handlers — keeps the graph
internals private to this module.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nodes import (
    decide_route,
    grade_documents_node,
    grade_generation_node,
    generate_node,
    refuse_node,
    retrieve_node,
)
from app.agents.state import AgentState

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _compile_graph() -> Any:
    """Compile once and reuse — graph construction is expensive."""
    graph = StateGraph(AgentState)

    # Nodes that need the DB session receive it via closures at run time;
    # to keep the graph itself stateless we wrap retrieve_node inline below.
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade_documents", grade_documents_node)
    graph.add_node("generate", generate_node)
    graph.add_node("grade_generation", grade_generation_node)
    graph.add_node("refuse", refuse_node)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges(
        "grade_documents",
        decide_route,
        {"generate": "generate", "refuse": "refuse"},
    )
    graph.add_edge("generate", "grade_generation")
    graph.add_edge("grade_generation", END)
    graph.add_edge("refuse", END)

    return graph.compile()


async def run_agent(*, question: str, session: AsyncSession) -> dict:
    """Run the full RAG flow for a single question.

    Returns `{answer, grounded, sources}` ready to be serialised by FastAPI.
    The DB session is injected into the `retrieve` node by wrapping the
    compiled graph behind a small adapter that re-runs `retrieve` manually.
    """
    started = time.monotonic()

    # Step 1: retrieval needs the session — do it outside the graph.
    initial: AgentState = {"question": question}
    retrieve_update = await retrieve_node(initial, session=session)
    state: AgentState = {**initial, **retrieve_update}

    # Step 2: run the remainder of the graph (it does not need the session).
    graph = _compile_graph()
    # We re-enter the graph at `grade_documents` by short-circuiting:
    # easier to just run the remaining nodes inline since LangGraph cannot
    # easily resume at an arbitrary node without a checkpointer.
    state = {**state, **(await grade_documents_node(state))}

    if decide_route(state) == "refuse":
        state = {**state, **refuse_node(state)}
    else:
        state = {**state, **(await generate_node(state))}
        state = {**state, **(await grade_generation_node(state))}

    elapsed = time.monotonic() - started
    log.info(
        "run_agent: completed in %.1fs grounded=%s",
        elapsed,
        bool(state.get("is_grounded")),
    )

    relevant = state.get("relevant") or []
    sources = [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "filename": c.document_filename,
            "similarity": round(c.similarity, 4),
            "snippet": c.content[:240],
        }
        for c in relevant
    ]
    return {
        "answer": state.get("generation", ""),
        "grounded": bool(state.get("is_grounded")),
        "sources": sources if state.get("is_grounded") else [],
    }
