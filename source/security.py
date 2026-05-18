from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def expires_at_iso(hours: int) -> str:
    return (utc_now() + timedelta(hours=hours)).isoformat()


def create_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise ValueError("Please provide a valid email address.")
    return normalized


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = os.urandom(16)
    iterations = 390000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_text))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def verify_stripe_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    if not signature_header or not secret:
        return False
    parts = {}
    for chunk in signature_header.split(","):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts.setdefault(key.strip(), []).append(value.strip())
    timestamp = (parts.get("t") or [None])[0]
    signatures = parts.get("v1") or []
    if not timestamp or not signatures:
        return False
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)
