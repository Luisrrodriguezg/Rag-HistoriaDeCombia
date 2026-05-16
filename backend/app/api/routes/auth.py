"""Auth-introspection endpoints. The frontend uses /auth/me to display the
current user and to bounce the user back to login when the token expires.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", summary="Current authenticated user")
async def me(user: CurrentUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": list(user.roles),
    }
