from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


def issue_rag_scope_token(
    *,
    secret: str,
    user_id: str,
    resource_types: tuple[str, ...],
    include_public: bool = True,
    lifetime_seconds: int = 60,
    now: int | None = None,
) -> str:
    if not secret:
        raise ValueError("RAG scope token secret is required")
    issued_at = int(time.time()) if now is None else int(now)
    payload = {
        "v": 1,
        "tenant_id": "default",
        "sub": user_id,
        "resource_types": list(resource_types),
        "include_public": bool(include_public),
        "iat": issued_at,
        "exp": issued_at + max(1, min(300, int(lifetime_seconds))),
    }
    encoded = _encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )
    digest = hmac.new(
        secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{_encode(digest)}"


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
