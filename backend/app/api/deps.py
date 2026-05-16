"""FastAPI dependencies shared across routers."""

from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.exceptions import InvalidJWT
from app.core.security import AuthenticatedUser, verify_token


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    """Extract and verify the bearer token from the `Authorization` header.

    Raises `InvalidJWT` (→ HTTP 401) for any missing/malformed/invalid token.
    """
    if not authorization:
        raise InvalidJWT("Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise InvalidJWT("Authorization header must use the Bearer scheme.")

    return await verify_token(token)


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
