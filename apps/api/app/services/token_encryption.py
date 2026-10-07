"""Encrypt/decrypt calendar OAuth refresh tokens at rest.

Uses Fernet (symmetric, from the `cryptography` package — already a
transitive dependency via `python-jose[cryptography]`, so this adds no new
top-level dependency). Keyed from settings.calendar_token_encryption_key,
generated once via `Fernet.generate_key()` and set as CALENDAR_TOKEN_
ENCRYPTION_KEY — never derived from jwt_secret or any other existing secret.

Raises (does not silently no-op) when the key is missing/invalid — callers
(routers/calendar.py) catch this and return 503, matching this repo's
degraded-mode convention (Trap #4) rather than storing/returning a plaintext
token because encryption "failed open".
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from core.config import settings


class TokenEncryptionUnavailable(RuntimeError):
    """CALENDAR_TOKEN_ENCRYPTION_KEY is unset or malformed."""


def _get_fernet() -> Fernet:
    key = settings.calendar_token_encryption_key
    if not key:
        raise TokenEncryptionUnavailable("CALENDAR_TOKEN_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise TokenEncryptionUnavailable(f"CALENDAR_TOKEN_ENCRYPTION_KEY is malformed: {exc}") from exc


def encrypt_token(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenEncryptionUnavailable("stored token could not be decrypted — key may have rotated") from exc
