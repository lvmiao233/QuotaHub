from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken

ENCRYPTED_PREFIX = "fernet:v1:"
ADMIN_TOKEN_ENV = "QUOTAHUB_ADMIN_TOKEN"
ENCRYPTION_KEY_ENV = "QUOTAHUB_ENCRYPTION_KEY"
DISALLOWED_ADMIN_TOKENS = {
    "replace-with-a-random-admin-token-at-least-32-characters",
}


class SecretConfigurationError(ValueError):
    pass


def admin_token() -> str:
    token = os.environ.get(ADMIN_TOKEN_ENV, "").strip()
    if len(token) < 32 or token in DISALLOWED_ADMIN_TOKENS:
        raise SecretConfigurationError(
            f"{ADMIN_TOKEN_ENV} must contain at least 32 non-placeholder characters"
        )
    return token


def _fernet() -> Fernet:
    raw_key = os.environ.get(ENCRYPTION_KEY_ENV, "").strip()
    if not raw_key:
        raise SecretConfigurationError(f"{ENCRYPTION_KEY_ENV} is required")
    try:
        return Fernet(raw_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise SecretConfigurationError(
            f"{ENCRYPTION_KEY_ENV} must be a valid Fernet key"
        ) from exc


def _fernet_key_bytes() -> bytes:
    raw_key = os.environ.get(ENCRYPTION_KEY_ENV, "").strip()
    _fernet()
    try:
        decoded = base64.urlsafe_b64decode(raw_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise SecretConfigurationError(
            f"{ENCRYPTION_KEY_ENV} must be a valid Fernet key"
        ) from exc
    if len(decoded) != 32:
        raise SecretConfigurationError(
            f"{ENCRYPTION_KEY_ENV} must be a valid Fernet key"
        )
    return decoded


def keyed_fingerprint(purpose: str, value: str) -> str:
    purpose_bytes = purpose.strip().encode("utf-8")
    if not purpose_bytes:
        raise ValueError("fingerprint purpose must not be empty")
    derived_key = hmac.new(
        _fernet_key_bytes(),
        b"quotahub-key-derivation:v1\x00" + purpose_bytes,
        hashlib.sha256,
    ).digest()
    digest = hmac.new(derived_key, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac:v1:{digest}"


def admin_token_fingerprint() -> str:
    return keyed_fingerprint("admin-token", admin_token())


def validate_runtime_secrets() -> None:
    admin_token()
    _fernet()


def is_encrypted(value: str) -> bool:
    return value.startswith(ENCRYPTED_PREFIX)


def encrypt_secret(value: str) -> str:
    if is_encrypted(value):
        decrypt_secret(value)
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    if not is_encrypted(value):
        raise SecretConfigurationError("stored credential is not encrypted")
    token = value[len(ENCRYPTED_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise SecretConfigurationError(
            "stored credential cannot be decrypted with QUOTAHUB_ENCRYPTION_KEY"
        ) from exc
