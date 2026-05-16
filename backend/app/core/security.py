"""Keycloak JWT verification.

We validate tokens locally against Keycloak's JWKS (RS256 only). The JWKS is
cached in memory and refreshed lazily — if a previously-unseen `kid` shows up
we re-fetch once before declaring the token invalid (handles realm key
rotation transparently).

We deliberately accept *either* the container-internal issuer
(http://keycloak:8080/...) or the browser-facing one (http://localhost:8080/...)
because in dev the frontend obtains tokens via the external URL while the
backend resolves Keycloak through Docker DNS.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import get_settings
from app.core.exceptions import InvalidJWT

log = logging.getLogger(__name__)

_JWKS_CACHE: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_LOCK = asyncio.Lock()
_JWKS_TTL_SECONDS = 60 * 10  # 10 minutes


@dataclass(frozen=True)
class AuthenticatedUser:
    """Lightweight projection of the JWT claims we actually use downstream."""

    sub: str
    username: str
    email: str | None
    roles: tuple[str, ...]

    @property
    def id(self) -> str:
        return self.sub


async def _fetch_jwks(force: bool = False) -> dict[str, Any]:
    settings = get_settings()
    async with _JWKS_LOCK:
        fresh = (
            _JWKS_CACHE["keys"] is not None
            and (time.time() - _JWKS_CACHE["fetched_at"]) < _JWKS_TTL_SECONDS
        )
        if fresh and not force:
            return _JWKS_CACHE["keys"]

        log.info("Fetching Keycloak JWKS from %s", settings.keycloak_internal_jwks_url)
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(settings.keycloak_internal_jwks_url)
            resp.raise_for_status()
            jwks = resp.json()

        _JWKS_CACHE["keys"] = jwks
        _JWKS_CACHE["fetched_at"] = time.time()
        return jwks


def _select_signing_key(jwks: dict[str, Any], token: str) -> dict[str, Any] | None:
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise InvalidJWT("Malformed token header.", details={"reason": str(exc)}) from exc

    kid = unverified_header.get("kid")
    if kid is None:
        raise InvalidJWT("Token header is missing `kid`.")

    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def verify_token(token: str) -> AuthenticatedUser:
    """Validate a JWT and return the projected user.

    Raises `InvalidJWT` on any verification failure. Callers (the FastAPI
    dependency in `app.api.deps`) translate this into HTTP 401 via the
    exception handler registered in `app.core.exceptions`.
    """
    settings = get_settings()
    accepted_issuers = {
        settings.keycloak_internal_issuer,
        settings.keycloak_external_issuer,
    }

    jwks = await _fetch_jwks()
    key = _select_signing_key(jwks, token)
    if key is None:
        # Possible key rotation — refresh once and retry.
        jwks = await _fetch_jwks(force=True)
        key = _select_signing_key(jwks, token)
    if key is None:
        raise InvalidJWT("Signing key not found in JWKS.")

    try:
        # Keycloak public clients don't include an `aud` claim by default
        # (the audience is typically the realm itself or absent). Disabling
        # the audience check avoids false negatives in the demo realm.
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise InvalidJWT("Token signature is invalid.", details={"reason": str(exc)}) from exc

    issuer = claims.get("iss")
    if issuer not in accepted_issuers:
        raise InvalidJWT(
            "Token issuer is not trusted.",
            details={"iss": issuer, "expected_any_of": list(accepted_issuers)},
        )

    sub = claims.get("sub")
    if not sub:
        raise InvalidJWT("Token is missing `sub` claim.")

    realm_access = claims.get("realm_access") or {}
    roles: list[str] = realm_access.get("roles", [])

    return AuthenticatedUser(
        sub=sub,
        username=claims.get("preferred_username") or sub,
        email=claims.get("email"),
        roles=tuple(roles),
    )
