"""Persistence of chat turns (one row per question/answer pair)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage


async def append_message(
    session: AsyncSession,
    *,
    user_id: str,
    question: str,
    answer: str,
    grounded: bool,
    sources: list[dict],
) -> ChatMessage:
    msg = ChatMessage(
        user_id=user_id,
        question=question,
        answer=answer,
        grounded=grounded,
        sources=sources,
    )
    session.add(msg)
    await session.flush()
    return msg


async def list_history(
    session: AsyncSession,
    *,
    user_id: str,
    limit: int = 50,
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
