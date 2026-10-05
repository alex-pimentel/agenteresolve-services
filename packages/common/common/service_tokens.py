"""Gateway-issued session tokens (centralized login).

Flow: the user signs in once on the central login app (Clerk). The login app
exchanges the Clerk JWT at ``POST /api/auth/session`` for a long-lived
gateway session token. Tool frontends store that token in the browser
(``localStorage``) and send it as ``Bearer`` — they never load Clerk JS and
need no Clerk key. The gateway accepts both token kinds on every ``/api/*``
route, so direct API consumers can keep using Clerk JWTs.

Tokens are stateless HMAC JWTs (``iss=agenteresolve-gateway``,
``typ=gateway-session``). Logout adds the ``jti`` to a Redis denylist with
TTL = remaining lifetime (skipped when Redis is unconfigured).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from common.config import get_settings

ISSUER = "agenteresolve-gateway"
TYPE = "gateway-session"


class ServiceTokenError(RuntimeError):
    """Issued when a gateway session token is missing, invalid or revoked."""


def _secret() -> str:
    secret = get_settings().gateway_session_secret or ""
    if not secret:
        raise ServiceTokenError("Gateway session signing is not configured")
    return secret


def _denylist() -> Any | None:
    """Return a Redis client for the logout denylist, or None when unconfigured."""
    url = get_settings().redis_url
    if not url:
        return None
    try:
        import redis

        return redis.from_url(url, decode_responses=True)
    except Exception:  # noqa: BLE001 - logout stays best-effort
        return None


def issue_token(*, clerk_id: str, email: str | None = None) -> tuple[str, int, str]:
    """Issue a session token. Returns ``(token, expires_at_unix, jti)``."""
    import jwt

    settings = get_settings()
    now = int(time.time())
    expires_at = now + settings.gateway_session_ttl_seconds
    jti = uuid.uuid4().hex
    token = jwt.encode(
        {
            "iss": ISSUER,
            "typ": TYPE,
            "sub": clerk_id,
            "email": email,
            "jti": jti,
            "iat": now,
            "exp": expires_at,
        },
        _secret(),
        algorithm="HS256",
    )
    return token, expires_at, jti


def verify_token(token: str) -> dict[str, Any]:
    """Verify signature/expiry/type and denylist. Returns the claims."""
    import jwt

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "iss", "sub", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise ServiceTokenError("Invalid or expired session token") from exc
    if claims.get("typ") != TYPE:
        raise ServiceTokenError("Not a gateway session token")
    client = _denylist()
    if client is not None:
        try:
            if client.get(f"gateway-denylist:{claims['jti']}"):
                raise ServiceTokenError("Session token was revoked")
        except ServiceTokenError:
            raise
        except Exception:  # noqa: BLE001 - denylist lookup stays best-effort
            pass
    return claims


def revoke_token(token: str) -> bool:
    """Deny-list a session token until its natural expiry. Returns True if stored."""
    import jwt

    try:
        claims: dict[str, Any] = jwt.decode(
            token, options={"verify_signature": False}, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return False
    if claims.get("iss") != ISSUER or claims.get("typ") != TYPE:
        return False
    client = _denylist()
    if client is None:
        return False
    ttl = max(1, int(claims.get("exp", 0)) - int(time.time()))
    try:
        client.set(f"gateway-denylist:{claims.get('jti')}", "1", ex=ttl)
        return True
    except Exception:  # noqa: BLE001 - logout stays best-effort
        return False


def looks_like_service_token(token: str) -> bool:
    """Cheap pre-check (unverified decode) to pick the verification path."""
    import jwt

    try:
        claims: dict[str, Any] = jwt.decode(
            token, options={"verify_signature": False}, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return False
    return claims.get("iss") == ISSUER and claims.get("typ") == TYPE
