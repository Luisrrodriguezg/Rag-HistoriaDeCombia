"""`chat_messages` table — persisted conversation history per user."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class ChatMessage(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"

    # Keycloak `sub`.
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Sources used to build the answer — list of {document_id, chunk_id, snippet}.
    sources: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
