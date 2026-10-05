"""Clerk JWT + gateway session verification.

``get_optional_user`` keeps the historical behavior (anonymous when no token or
when Clerk is unconfigured) and is used by the public ``/health`` probe only.

``get_required_user`` enforces authentication on every ``/api/*`` route and
accepts **both** token kinds: Clerk session JWTs (direct API consumers) and
gateway session tokens issued by ``POST /api/auth/session`` (browser
frontends after the central login). Set ``AUTH_REQUIRED=false`` for local
development without Clerk.
"""

from __future__ import annotations

from typing import Any

import jwt
from common.config import get_settings
from common.service_tokens import ServiceTokenError, looks_like_service_token, verify_token
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient, PyJWTError


def _verify(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        jwks_client = PyJWKClient(settings.clerk_jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.clerk_audience,
            issuer=settings.clerk_issuer,
            options={"verify_aud": bool(settings.clerk_audience)},
        )
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_optional_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any] | None:
    if not authorization:
        return None  # anonymous

    if not get_settings().clerk_jwks_url:
        return None  # auth not configured; treat as anonymous

    token = authorization.removeprefix("Bearer ").strip()
    return _verify(token)


def get_required_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    settings = get_settings()

    if not settings.auth_required:
        if not authorization:
            return {"sub": "local-dev", "email": None}
        if not settings.clerk_jwks_url:
            return {"sub": "local-dev", "email": None}

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required: sign in to use this tool.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()
    if looks_like_service_token(token):
        try:
            return verify_token(token)
        except ServiceTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
    return _verify(token)
