"""Liveness/readiness endpoints — intentionally unauthenticated so Docker and
upstream load balancers can probe the service without a JWT.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}
