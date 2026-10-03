"""Optional Clerk JWT verification.

Anonymous access is allowed. When ``CLERK_JWKS_URL`` is configured and an
``Authorization: Bearer <token>`` header is present, the token is verified against the
Clerk JWKS; invalid tokens are rejected with 401.
"""

from __future__ import annotations

from typing import Any

import jwt
from common.config import get_settings
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient, PyJWTError


def get_optional_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    settings = get_settings()

    if not authorization:
        return None  # anonymous

    if not settings.clerk_jwks_url:
        return None  # auth not configured; treat as anonymous

    token = authorization.removeprefix("Bearer ").strip()
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
