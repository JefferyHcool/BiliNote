import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Optional

from fastapi import Request


AUTH_COOKIE_NAME = "bilinote_auth"
AUTH_SUBJECT = "self-host"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_auth_enabled() -> bool:
    """Whether the optional self-host single-user auth gate is enabled."""
    return _truthy(os.getenv("BILINOTE_AUTH_ENABLED"))


def get_auth_password() -> str:
    return os.getenv("BILINOTE_AUTH_PASSWORD", "")


def get_token_max_age_seconds() -> int:
    days = int(os.getenv("BILINOTE_AUTH_TOKEN_EXPIRE_DAYS", "30") or "30")
    return max(days, 1) * 24 * 60 * 60


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _get_secret() -> bytes:
    """Return the HMAC secret.

    A dedicated BILINOTE_AUTH_SECRET keeps tokens valid when the password is
    rotated. If it is not configured we derive a deterministic secret from the
    self-host password, which is sufficient for the single-user deployment gate.
    """
    configured = os.getenv("BILINOTE_AUTH_SECRET")
    if configured:
        return configured.encode("utf-8")
    password = get_auth_password()
    return hashlib.sha256(f"bilinote-auth:{password}".encode("utf-8")).digest()


def check_password(password: str) -> bool:
    expected = get_auth_password()
    if not expected:
        return False
    return hmac.compare_digest(password or "", expected)


def create_access_token() -> str:
    now = int(time.time())
    payload = {
        "sub": AUTH_SUBJECT,
        "iat": now,
        "exp": now + get_token_max_age_seconds(),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(_get_secret(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}"


def verify_access_token(token: str | None) -> Optional[dict[str, Any]]:
    if not token or "." not in token:
        return None
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(_get_secret(), body.encode("ascii"), hashlib.sha256).digest()
        provided = _b64url_decode(sig)
        if not hmac.compare_digest(provided, expected):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if payload.get("sub") != AUTH_SUBJECT:
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    # Used by extension-rendered images where <img> cannot attach an
    # Authorization header. Keep it optional and only accept signed tokens.
    query_token = request.query_params.get("access_token")
    if query_token:
        return query_token
    return None


def is_request_authenticated(request: Request) -> bool:
    if not is_auth_enabled():
        return True
    return verify_access_token(extract_token(request)) is not None

