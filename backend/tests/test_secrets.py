from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from app import db
from app.bootstrap import ensure_bootstrapped
from app.secrets import (
    SecretConfigurationError,
    decrypt_secret,
    encrypt_secret,
    is_encrypted,
    validate_runtime_secrets,
)


def test_encrypt_round_trip_and_random_ciphertext(temp_data_dir):
    first = encrypt_secret("management-key")
    second = encrypt_secret("management-key")

    assert is_encrypted(first)
    assert first != second
    assert "management-key" not in first
    assert decrypt_secret(first) == "management-key"


def test_runtime_secrets_are_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("QUOTAHUB_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("QUOTAHUB_ENCRYPTION_KEY", raising=False)
    with pytest.raises(SecretConfigurationError):
        validate_runtime_secrets()


def test_public_placeholder_admin_token_is_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "QUOTAHUB_ADMIN_TOKEN",
        "replace-with-a-random-admin-token-at-least-32-characters",
    )
    monkeypatch.setenv("QUOTAHUB_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    with pytest.raises(SecretConfigurationError, match="non-placeholder"):
        validate_runtime_secrets()


def test_wrong_encryption_key_is_rejected(temp_data_dir, monkeypatch: pytest.MonkeyPatch):
    encrypted = encrypt_secret("secret")
    monkeypatch.setenv("QUOTAHUB_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    with pytest.raises(SecretConfigurationError, match="cannot be decrypted"):
        decrypt_secret(encrypted)


def test_account_secrets_are_encrypted_in_sqlite(temp_data_dir):
    opencode = db.create_opencode_account(
        name="OpenCode", workspace_id="Default", auth_cookie="auth=plain-cookie"
    )
    ollama = db.create_ollama_account(
        name="Ollama", session_cookie="__Secure-session=plain-session"
    )

    with sqlite3.connect(db.db_path()) as conn:
        stored_open = conn.execute(
            "SELECT auth_cookie FROM opencode_accounts WHERE id = ?", (opencode.id,)
        ).fetchone()[0]
        stored_ollama = conn.execute(
            "SELECT session_cookie FROM ollama_accounts WHERE id = ?", (ollama.id,)
        ).fetchone()[0]

    assert stored_open.startswith("fernet:v1:")
    assert stored_ollama.startswith("fernet:v1:")
    assert "plain-cookie" not in stored_open
    assert "plain-session" not in stored_ollama
    assert db.get_opencode_account(opencode.id).auth_cookie == "auth=plain-cookie"
    assert db.get_ollama_account(ollama.id).session_cookie == "__Secure-session=plain-session"


def test_bootstrap_migrates_plaintext_credentials(temp_data_dir):
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(db.db_path()) as conn:
        conn.execute(
            """
            INSERT INTO opencode_accounts (
                id, name, workspace_id, auth_cookie, created_at, updated_at
            ) VALUES ('legacy', 'Legacy', 'Default', 'auth=legacy-secret', ?, ?)
            """,
            (now, now),
        )
        conn.commit()

    ensure_bootstrapped()
    ensure_bootstrapped()

    with sqlite3.connect(db.db_path()) as conn:
        stored = conn.execute(
            "SELECT auth_cookie FROM opencode_accounts WHERE id = 'legacy'"
        ).fetchone()[0]
    assert stored.startswith("fernet:v1:")
    assert "legacy-secret" not in stored
    assert db.get_opencode_account("legacy").auth_cookie == "auth=legacy-secret"


def test_bootstrap_migrates_plaintext_cpa_management_key_idempotently(temp_data_dir):
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(db.db_path()) as conn:
        conn.execute(
            """
            INSERT INTO cpa_channels (
                id, public_id, name, base_url, management_key,
                created_at, updated_at
            ) VALUES (
                'legacy-cpa', 'legacy-cpa-public', 'Legacy CPA',
                'https://cpa.example.test', 'legacy-management-key', ?, ?
            )
            """,
            (now, now),
        )
        conn.commit()

    ensure_bootstrapped()
    ensure_bootstrapped()

    with sqlite3.connect(db.db_path()) as conn:
        stored = conn.execute(
            "SELECT management_key FROM cpa_channels WHERE id = 'legacy-cpa'"
        ).fetchone()[0]
    assert stored.startswith("fernet:v1:")
    assert "legacy-management-key" not in stored
    assert db.get_cpa_channel("legacy-cpa").management_key == "legacy-management-key"


def test_plaintext_migration_rewrites_sqlite_pages_and_sidecars(temp_data_dir):
    sentinel = "physical-plaintext-sentinel-" + ("x" * 512)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(db.db_path()) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            """
            INSERT INTO opencode_accounts (
                id, name, workspace_id, auth_cookie, created_at, updated_at
            ) VALUES ('physical-legacy', 'Physical Legacy', 'Default', ?, ?, ?)
            """,
            (sentinel, now, now),
        )
        conn.commit()

    targets = [
        db.db_path(),
        db.db_path().with_name(db.db_path().name + "-wal"),
        db.db_path().with_name(db.db_path().name + "-journal"),
    ]
    sentinel_bytes = sentinel.encode("utf-8")
    assert any(path.exists() and sentinel_bytes in path.read_bytes() for path in targets)

    ensure_bootstrapped()

    for path in targets:
        if path.exists():
            assert sentinel_bytes not in path.read_bytes()
    assert db.get_opencode_account("physical-legacy").auth_cookie == sentinel


def test_admin_session_lifecycle(temp_data_dir):
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    db.create_admin_session("hash", expires)
    assert db.get_admin_session("hash") is not None
    db.touch_admin_session("hash")
    assert db.delete_admin_session("hash") is True
    assert db.get_admin_session("hash") is None


def test_expired_admin_sessions_are_purged(temp_data_dir):
    expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    db.create_admin_session("expired", expired)
    assert db.purge_expired_admin_sessions() == 1
    assert db.get_admin_session("expired") is None


def test_admin_token_rotation_revokes_sessions(
    temp_data_dir, monkeypatch: pytest.MonkeyPatch
):
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    ensure_bootstrapped()
    db.create_admin_session("same-token-session", expires)

    ensure_bootstrapped()
    assert db.get_admin_session("same-token-session") is not None

    monkeypatch.setenv(
        "QUOTAHUB_ADMIN_TOKEN", "rotated-admin-token-with-at-least-32-characters"
    )
    ensure_bootstrapped()
    assert db.get_admin_session("same-token-session") is None

    db.create_admin_session("rotated-token-session", expires)
    ensure_bootstrapped()
    assert db.get_admin_session("rotated-token-session") is not None
