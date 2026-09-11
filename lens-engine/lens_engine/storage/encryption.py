"""At-rest encryption option (§13 Privacy).

When ``LENS_ENCRYPTION_KEY`` is set (a Fernet key), raw image bytes are
encrypted before they touch disk and decrypted on every read through
:func:`vision.ingest.read_image_bytes`. When unset, bytes are stored plain —
the option exists for shared-lab machines, not as a default.

Graceful degradation: if the optional ``cryptography`` package is missing but
a key was provided, we fail loudly at startup rather than silently storing
plaintext under the user's encryption assumption.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets

_PREFIX = b"LENC1:"  # magic prefix so encrypted vs plain files are distinguishable


def _fernet(key: str):
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "LENS_ENCRYPTION_KEY is set but the 'cryptography' package is not installed. "
            "Install lens-engine[encryption] or unset the key."
        ) from e
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_bytes(raw: bytes, key: str | None) -> bytes:
    if not key:
        return raw
    f = _fernet(key)
    return _PREFIX + f.encrypt(raw)


def decrypt_bytes(blob: bytes, key: str | None) -> bytes:
    if not blob.startswith(_PREFIX):
        return blob  # stored plain (key added later, or never encrypted)
    if not key:
        raise RuntimeError(
            "Data on disk is encrypted but LENS_ENCRYPTION_KEY is not set. "
            "Provide the same key used at ingest time."
        )
    f = _fernet(key)
    return f.decrypt(blob[len(_PREFIX):])


def generate_key() -> str:
    """Generate a Fernet key (used by the Settings UI / first-run hint)."""
    try:
        from cryptography.fernet import Fernet

        return Fernet.generate_key().decode()
    except ImportError:
        # Deterministic fallback derivation from os randomness (rare path:
        # cryptography missing). 32 url-safe bytes, base64 — Fernet-compatible
        # only when cryptography is installed later; documented as such.
        raw = secrets.token_bytes(32)
        return base64.urlsafe_b64encode(raw).decode()


def key_fingerprint(key: str | None) -> str | None:
    """Short, non-reversible fingerprint for the Settings screen ('encryption: on (a1b2c3)')."""
    if not key:
        return None
    return hashlib.sha256(key.encode()).hexdigest()[:6]
