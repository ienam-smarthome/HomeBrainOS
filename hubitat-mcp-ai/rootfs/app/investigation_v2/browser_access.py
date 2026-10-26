"""Optional revocable browser access for the explicitly gated V2 test page.

A remembered browser receives a short-lived HMAC-authenticated *session
credential*, never the original operator token. It is intentionally stateless:
rotating the configured secret immediately invalidates old browser access.
No localStorage, cookie-accessible JavaScript or DB persistence is required.

The cookie is still a bearer credential. Use only on a trusted browser and
prefer HTTPS; LAN HTTP does not provide transport confidentiality.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

COOKIE_NAME = "homebrain_v2_browser_access"
COOKIE_AGE_SECONDS = 30 * 24 * 3600
_COOKIE_DOMAIN = b"HomeBrainOS-v2-browser-access-v1|"


def mint_browser_access(secret: str, *, now: int | None = None) -> str:
    if not isinstance(secret, str) or len(secret) < 16:
        raise ValueError("V2 access is not configured")
    issued = int(time.time()) if now is None else int(now)
    nonce = secrets.token_hex(16)
    body = f"v1.{issued}.{nonce}"
    signature = hmac.new(
        secret.encode("utf-8"), _COOKIE_DOMAIN + body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{signature}"


def verify_browser_access(
    candidate: str | None, secret: str, *, now: int | None = None,
) -> bool:
    if (not isinstance(candidate, str) or len(candidate) > 180
            or not isinstance(secret, str) or len(secret) < 16):
        return False
    parts = candidate.split(".")
    if len(parts) != 4 or parts[0] != "v1":
        return False
    _, issued, nonce, signature = parts
    if (not issued.isascii() or not issued.isdecimal() or
            len(issued) > 12 or len(nonce) != 32 or len(signature) != 64 or
            any(ch not in "0123456789abcdef" for ch in nonce+signature)):
        return False
    current = int(time.time()) if now is None else int(now)
    created = int(issued)
    if created > current + 60 or current - created > COOKIE_AGE_SECONDS:
        return False
    message = _COOKIE_DOMAIN + ".".join(parts[:3]).encode("ascii")
    expected = hmac.new(
        secret.encode("utf-8"), message, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


__all__ = [
    "COOKIE_NAME", "COOKIE_AGE_SECONDS", "mint_browser_access",
    "verify_browser_access",
]
