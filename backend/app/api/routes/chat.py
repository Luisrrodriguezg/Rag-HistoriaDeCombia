"""/chat endpoints — protected by current_user dependency."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.agents.graph import run_agent, run_agent_stream
from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.repositories import chat_repo
from app.schemas.chat import ChatHistoryItem, ChatRequest, ChatResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


async def _recent_history(session, user_id: str) -> list[dict]:
    """Fetch the last N (question, answer) pairs in chronological order.

    `chat_repo.list_history` returns newest-first; we reverse to chronological
    so the LLM reads the conversation in natural order. N is configurable via
    `CHAT_HISTORY_TURNS` (default 3).
    """
    n = get_settings().chat_history_turns
    if n <= 0:
        return []
    rows = await chat_repo.list_history(session, user_id=user_id, limit=n)
    rows = list(reversed(rows))  # oldest first
    return [{"question": r.question, "answer": r.answer} for r in rows]


@router.post("", response_model=ChatResponse, summary="Ask the agent a question")
async def ask(
    payload: ChatRequest,
    user: CurrentUser,
    session: DbSession,
) -> ChatResponse:
    history = await _recent_history(session, user.id)
    result = await run_agent(
        question=payload.question, session=session, history=history
    )

    await chat_repo.append_message(
        session,
        user_id=user.id,
        question=payload.question,
        answer=result["answer"],
        grounded=result["grounded"],
        sources=result["sources"],
    )
    await session.commit()

    return ChatResponse(**result)


@router.post(
    "/stream",
    summary="Ask the agent a question — streams tokens as SSE",
)
async def ask_stream(
    payload: ChatRequest,
    user: CurrentUser,
    session: DbSession,
) -> StreamingResponse:
    """Server-Sent Events endpoint.

    Emits `data: {json}\\n\\n` lines: zero or more `{type: "token"}` events
    followed by exactly one `{type: "done"}` event carrying the final answer,
    grounded flag, and sources. The full turn is persisted to the chat history
    once the `done` event fires.
    """

    history = await _recent_history(session, user.id)

    async def event_stream():
        final: dict | None = None
        try:
            async for event in run_agent_stream(
                question=payload.question, session=session, history=history
            ):
                if event.get("type") == "done":
                    final = event
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if final is not None:
                await chat_repo.append_message(
                    session,
                    user_id=user.id,
                    question=payload.question,
                    answer=final["answer"],
                    grounded=final["grounded"],
                    sources=final["sources"],
                )
                await session.commit()
        except Exception as exc:
            log.exception("chat stream failed")
            err = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/history",
    response_model=list[ChatHistoryItem],
    summary="Return the latest chat turns for the current user",
)
async def history(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ChatHistoryItem]:
    items = await chat_repo.list_history(session, user_id=user.id, limit=limit)
    return [
        ChatHistoryItem(
            id=str(m.id),
            question=m.question,
            answer=m.answer,
            grounded=m.grounded,
            sources=m.sources,
            created_at=m.created_at,
        )
        for m in items
    ]
