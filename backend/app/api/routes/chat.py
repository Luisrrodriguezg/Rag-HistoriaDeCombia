"""/chat endpoints — protected by current_user dependency."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.agents.graph import run_agent
from app.api.deps import CurrentUser, DbSession
from app.repositories import chat_repo
from app.schemas.chat import ChatHistoryItem, ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="Ask the agent a question")
async def ask(
    payload: ChatRequest,
    user: CurrentUser,
    session: DbSession,
) -> ChatResponse:
    result = await run_agent(question=payload.question, session=session)

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
