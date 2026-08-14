from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from .config import data_dir
from .secrets import decrypt_secret, encrypt_secret, is_encrypted


class CollectionGuardRejected(RuntimeError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def db_path() -> Path:
    return data_dir() / "quotahub.db"


def imported_flag_path() -> Path:
    return data_dir() / ".imported"


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _validate_collection_guard(
    conn: sqlite3.Connection,
    *,
    source_table: str,
    source_id: str,
    expected_collection_revision: int | None,
    lease_name: str | None,
    lease_owner_id: str | None,
) -> None:
    if (lease_name is None) != (lease_owner_id is None):
        raise ValueError("lease name and owner must be provided together")
    if expected_collection_revision is not None:
        row = conn.execute(
            f"SELECT enabled, collection_revision FROM {source_table} WHERE id = ?",
            (source_id,),
        ).fetchone()
        if (
            row is None
            or not bool(row["enabled"])
            or int(row["collection_revision"]) != expected_collection_revision
        ):
            raise CollectionGuardRejected("source_changed")
    if lease_name is not None and lease_owner_id is not None:
        row = conn.execute(
            """
            SELECT 1 FROM scheduler_leases
            WHERE name = ? AND owner_id = ? AND expires_at > ?
            """,
            (lease_name, lease_owner_id, _now_iso()),
        ).fetchone()
        if row is None:
            raise CollectionGuardRejected("lease_lost")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS opencode_accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace_id TEXT NOT NULL DEFAULT 'Default',
                resolved_workspace_id TEXT,
                auth_cookie TEXT NOT NULL,
                show_rolling INTEGER NOT NULL DEFAULT 1,
                show_weekly INTEGER NOT NULL DEFAULT 1,
                show_monthly INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                collection_revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ollama_accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                session_cookie TEXT NOT NULL,
                show_session INTEGER NOT NULL DEFAULT 1,
                show_weekly INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                collection_revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usage_records (
                usg_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES opencode_accounts(id) ON DELETE CASCADE,
                workspace_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                model TEXT NOT NULL,
                provider TEXT,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_raw INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                key_id TEXT,
                plan TEXT,
                synced_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_usage_account_time
                ON usage_records(account_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_usage_account_key
                ON usage_records(account_id, key_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS usage_sync_state (
                account_id TEXT PRIMARY KEY REFERENCES opencode_accounts(id) ON DELETE CASCADE,
                last_sync_at TEXT,
                last_sync_status TEXT,
                last_sync_error TEXT,
                last_inserted_count INTEGER NOT NULL DEFAULT 0,
                deepest_page_fetched INTEGER NOT NULL DEFAULT -1,
                total_records INTEGER NOT NULL DEFAULT 0,
                oldest_record_at TEXT,
                newest_record_at TEXT
            );

            CREATE TABLE IF NOT EXISTS opencode_quota_snapshots (
                account_id TEXT PRIMARY KEY REFERENCES opencode_accounts(id) ON DELETE CASCADE,
                public_id TEXT NOT NULL UNIQUE,
                windows_json TEXT NOT NULL DEFAULT '[]',
                last_attempt_at TEXT,
                last_success_at TEXT,
                last_attempt_status TEXT,
                stale INTEGER NOT NULL DEFAULT 0,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS ollama_quota_snapshots (
                account_id TEXT PRIMARY KEY REFERENCES ollama_accounts(id) ON DELETE CASCADE,
                public_id TEXT NOT NULL UNIQUE,
                plan TEXT,
                windows_json TEXT NOT NULL DEFAULT '[]',
                last_attempt_at TEXT,
                last_success_at TEXT,
                last_attempt_status TEXT,
                stale INTEGER NOT NULL DEFAULT 0,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS cpa_channels (
                id TEXT PRIMARY KEY,
                public_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                management_key TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                collection_revision INTEGER NOT NULL DEFAULT 1,
                interval_sec INTEGER NOT NULL DEFAULT 1800,
                last_attempt_at TEXT,
                last_success_at TEXT,
                last_attempt_status TEXT,
                stale INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cpa_quota_snapshots (
                channel_id TEXT NOT NULL REFERENCES cpa_channels(id) ON DELETE CASCADE,
                account_key_hash TEXT NOT NULL,
                public_id TEXT NOT NULL UNIQUE,
                account_display TEXT NOT NULL,
                plan TEXT NOT NULL,
                windows_json TEXT NOT NULL DEFAULT '[]',
                visible INTEGER NOT NULL DEFAULT 1,
                last_attempt_at TEXT,
                last_success_at TEXT,
                last_attempt_status TEXT,
                stale INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                quota_source TEXT,
                observed_at TEXT,
                last_active_attempt_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (channel_id, account_key_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_cpa_snapshot_channel_visible
                ON cpa_quota_snapshots(channel_id, visible, created_at);

            CREATE TABLE IF NOT EXISTS service_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                token_hash TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_used_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS security_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_login_attempts (
                source_hmac TEXT NOT NULL,
                failed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_admin_login_attempts_source_time
                ON admin_login_attempts(source_hmac, failed_at);

            CREATE TABLE IF NOT EXISTS scheduler_leases (
                name TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        cpa_snapshot_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(cpa_quota_snapshots)"
            ).fetchall()
        }
        for column_name, column_type in (
            ("quota_source", "TEXT"),
            ("observed_at", "TEXT"),
            ("last_active_attempt_at", "TEXT"),
        ):
            if column_name not in cpa_snapshot_columns:
                conn.execute(
                    f"ALTER TABLE cpa_quota_snapshots ADD COLUMN {column_name} {column_type}"
                )
        for table in ("opencode_accounts", "ollama_accounts", "cpa_channels"):
            columns = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if "collection_revision" not in columns:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN collection_revision "
                    "INTEGER NOT NULL DEFAULT 1"
                )
        for row in conn.execute("SELECT id FROM opencode_accounts").fetchall():
            conn.execute(
                """
                INSERT OR IGNORE INTO opencode_quota_snapshots (account_id, public_id)
                VALUES (?, ?)
                """,
                (row["id"], str(uuid.uuid4())),
            )
        for row in conn.execute("SELECT id FROM ollama_accounts").fetchall():
            conn.execute(
                """
                INSERT OR IGNORE INTO ollama_quota_snapshots (account_id, public_id)
                VALUES (?, ?)
                """,
                (row["id"], str(uuid.uuid4())),
            )


@dataclass
class OpenCodeAccountRow:
    id: str
    name: str
    workspace_id: str
    resolved_workspace_id: str | None
    auth_cookie: str
    show_rolling: bool
    show_weekly: bool
    show_monthly: bool
    enabled: bool
    collection_revision: int
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> OpenCodeAccountRow:
        return cls(
            id=row["id"],
            name=row["name"],
            workspace_id=row["workspace_id"],
            resolved_workspace_id=row["resolved_workspace_id"],
            auth_cookie=decrypt_secret(row["auth_cookie"]),
            show_rolling=bool(row["show_rolling"]),
            show_weekly=bool(row["show_weekly"]),
            show_monthly=bool(row["show_monthly"]),
            enabled=bool(row["enabled"]),
            collection_revision=max(1, int(row["collection_revision"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class OllamaAccountRow:
    id: str
    name: str
    session_cookie: str
    show_session: bool
    show_weekly: bool
    enabled: bool
    collection_revision: int
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> OllamaAccountRow:
        return cls(
            id=row["id"],
            name=row["name"],
            session_cookie=decrypt_secret(row["session_cookie"]),
            show_session=bool(row["show_session"]),
            show_weekly=bool(row["show_weekly"]),
            enabled=bool(row["enabled"]),
            collection_revision=max(1, int(row["collection_revision"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class CPAChannelRow:
    id: str
    public_id: str
    name: str
    base_url: str
    management_key: str
    enabled: bool
    collection_revision: int
    interval_sec: int
    last_attempt_at: str | None
    last_success_at: str | None
    last_attempt_status: str | None
    stale: bool
    error: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CPAChannelRow:
        return cls(
            id=row["id"],
            public_id=row["public_id"],
            name=row["name"],
            base_url=row["base_url"],
            management_key=decrypt_secret(row["management_key"]),
            enabled=bool(row["enabled"]),
            collection_revision=max(1, int(row["collection_revision"])),
            interval_sec=max(300, int(row["interval_sec"])),
            last_attempt_at=row["last_attempt_at"],
            last_success_at=row["last_success_at"],
            last_attempt_status=row["last_attempt_status"],
            stale=bool(row["stale"]),
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class UsageRecordRow:
    usg_id: str
    account_id: str
    workspace_id: str
    created_at: str
    model: str
    provider: str | None
    input_tokens: int
    output_tokens: int
    cost_raw: int
    cost_usd: float
    key_id: str | None
    plan: str | None
    synced_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "usg_id": self.usg_id,
            "account_id": self.account_id,
            "created_at": self.created_at,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "key_id": self.key_id,
            "plan": self.plan,
        }


@dataclass
class UsageRecordWithAccount(UsageRecordRow):
    account_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["account_name"] = self.account_name
        return payload


@dataclass
class UsageSyncStateRow:
    account_id: str
    last_sync_at: str | None
    last_sync_status: str | None
    last_sync_error: str | None
    last_inserted_count: int
    deepest_page_fetched: int
    total_records: int
    oldest_record_at: str | None
    newest_record_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_sync_at": self.last_sync_at,
            "last_sync_status": self.last_sync_status,
            "last_sync_error": self.last_sync_error,
            "last_inserted_count": self.last_inserted_count,
            "deepest_page_fetched": self.deepest_page_fetched,
            "total_records": self.total_records,
            "oldest_record_at": self.oldest_record_at,
            "newest_record_at": self.newest_record_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row | None, account_id: str) -> UsageSyncStateRow:
        if row is None:
            return cls(
                account_id=account_id,
                last_sync_at=None,
                last_sync_status=None,
                last_sync_error=None,
                last_inserted_count=0,
                deepest_page_fetched=-1,
                total_records=0,
                oldest_record_at=None,
                newest_record_at=None,
            )
        return cls(
            account_id=account_id,
            last_sync_at=row["last_sync_at"],
            last_sync_status=row["last_sync_status"],
            last_sync_error=row["last_sync_error"],
            last_inserted_count=int(row["last_inserted_count"]),
            deepest_page_fetched=int(row["deepest_page_fetched"]),
            total_records=int(row["total_records"]),
            oldest_record_at=row["oldest_record_at"],
            newest_record_at=row["newest_record_at"],
        )


def list_opencode_accounts(*, enabled_only: bool = False) -> list[OpenCodeAccountRow]:
    with get_conn() as conn:
        sql = "SELECT * FROM opencode_accounts"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at ASC"
        rows = conn.execute(sql).fetchall()
    return [OpenCodeAccountRow.from_row(r) for r in rows]


def get_opencode_account(account_id: str) -> OpenCodeAccountRow | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM opencode_accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return OpenCodeAccountRow.from_row(row) if row else None


def create_opencode_account(
    *,
    name: str,
    workspace_id: str,
    auth_cookie: str,
    show_rolling: bool = True,
    show_weekly: bool = True,
    show_monthly: bool = True,
    enabled: bool = True,
) -> OpenCodeAccountRow:
    account_id = str(uuid.uuid4())
    now = _now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO opencode_accounts (
                id, name, workspace_id, resolved_workspace_id, auth_cookie,
                show_rolling, show_weekly, show_monthly, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                name,
                workspace_id,
                encrypt_secret(auth_cookie),
                int(show_rolling),
                int(show_weekly),
                int(show_monthly),
                int(enabled),
                now,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO usage_sync_state (account_id) VALUES (?)",
            (account_id,),
        )
        conn.execute(
            """
            INSERT INTO opencode_quota_snapshots (account_id, public_id)
            VALUES (?, ?)
            """,
            (account_id, str(uuid.uuid4())),
        )
    account = get_opencode_account(account_id)
    assert account is not None
    return account


def update_opencode_account(account_id: str, **fields: Any) -> OpenCodeAccountRow | None:
    allowed = {
        "name",
        "workspace_id",
        "resolved_workspace_id",
        "auth_cookie",
        "show_rolling",
        "show_weekly",
        "show_monthly",
        "enabled",
    }
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stored = conn.execute(
            "SELECT * FROM opencode_accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if stored is None:
            return None
        current = OpenCodeAccountRow.from_row(stored)
        changed: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed or (value is None and key != "resolved_workspace_id"):
                continue
            normalized = value
            if key == "auth_cookie":
                normalized = str(value)
            elif key in {"show_rolling", "show_weekly", "show_monthly", "enabled"}:
                normalized = bool(value)
            if getattr(current, key) != normalized:
                changed[key] = normalized
        collection_changed = bool(
            {"auth_cookie", "workspace_id", "enabled"} & changed.keys()
        )
        if {"auth_cookie", "workspace_id"} & changed.keys():
            changed["resolved_workspace_id"] = None
        if not changed:
            return current
        updates: list[str] = []
        values: list[Any] = []
        for key, value in changed.items():
            if key == "auth_cookie":
                value = encrypt_secret(str(value))
            elif key in {"show_rolling", "show_weekly", "show_monthly", "enabled"}:
                value = int(bool(value))
            updates.append(f"{key} = ?")
            values.append(value)
        if collection_changed:
            updates.append("collection_revision = collection_revision + 1")
        updates.append("updated_at = ?")
        values.extend((_now_iso(), account_id))
        conn.execute(
            f"UPDATE opencode_accounts SET {', '.join(updates)} WHERE id = ?",
            values,
        )
    return get_opencode_account(account_id)


def record_opencode_resolved_workspace(
    account_id: str,
    resolved_workspace_id: str,
    *,
    expected_collection_revision: int,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="opencode_accounts",
            source_id=account_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        conn.execute(
            """
            UPDATE opencode_accounts
            SET resolved_workspace_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (resolved_workspace_id, _now_iso(), account_id),
        )


def delete_opencode_account(account_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM opencode_accounts WHERE id = ?", (account_id,))
        return cur.rowcount > 0


def list_ollama_accounts(*, enabled_only: bool = False) -> list[OllamaAccountRow]:
    with get_conn() as conn:
        sql = "SELECT * FROM ollama_accounts"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at ASC"
        rows = conn.execute(sql).fetchall()
    return [OllamaAccountRow.from_row(r) for r in rows]


def get_ollama_account(account_id: str) -> OllamaAccountRow | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ollama_accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return OllamaAccountRow.from_row(row) if row else None


def create_ollama_account(
    *,
    name: str,
    session_cookie: str,
    show_session: bool = True,
    show_weekly: bool = True,
    enabled: bool = True,
) -> OllamaAccountRow:
    account_id = str(uuid.uuid4())
    now = _now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ollama_accounts (
                id, name, session_cookie, show_session, show_weekly, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                name,
                encrypt_secret(session_cookie),
                int(show_session),
                int(show_weekly),
                int(enabled),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO ollama_quota_snapshots (account_id, public_id)
            VALUES (?, ?)
            """,
            (account_id, str(uuid.uuid4())),
        )
    account = get_ollama_account(account_id)
    assert account is not None
    return account


def update_ollama_account(account_id: str, **fields: Any) -> OllamaAccountRow | None:
    allowed = {"name", "session_cookie", "show_session", "show_weekly", "enabled"}
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stored = conn.execute(
            "SELECT * FROM ollama_accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if stored is None:
            return None
        current = OllamaAccountRow.from_row(stored)
        changed: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed or value is None:
                continue
            normalized = str(value) if key == "session_cookie" else value
            if key in {"show_session", "show_weekly", "enabled"}:
                normalized = bool(value)
            if getattr(current, key) != normalized:
                changed[key] = normalized
        if not changed:
            return current
        updates: list[str] = []
        values: list[Any] = []
        for key, value in changed.items():
            if key == "session_cookie":
                value = encrypt_secret(str(value))
            elif key in {"show_session", "show_weekly", "enabled"}:
                value = int(bool(value))
            updates.append(f"{key} = ?")
            values.append(value)
        if {"session_cookie", "enabled"} & changed.keys():
            updates.append("collection_revision = collection_revision + 1")
        updates.append("updated_at = ?")
        values.extend((_now_iso(), account_id))
        conn.execute(
            f"UPDATE ollama_accounts SET {', '.join(updates)} WHERE id = ?",
            values,
        )
    return get_ollama_account(account_id)


def delete_ollama_account(account_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM ollama_accounts WHERE id = ?", (account_id,))
        return cur.rowcount > 0


def list_cpa_channels(*, enabled_only: bool = False) -> list[CPAChannelRow]:
    with get_conn() as conn:
        sql = "SELECT * FROM cpa_channels"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at ASC"
        rows = conn.execute(sql).fetchall()
    return [CPAChannelRow.from_row(row) for row in rows]


def get_cpa_channel(channel_id: str) -> CPAChannelRow | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM cpa_channels WHERE id = ?", (channel_id,)
        ).fetchone()
    return CPAChannelRow.from_row(row) if row else None


def create_cpa_channel(
    *,
    name: str,
    base_url: str,
    management_key: str,
    enabled: bool = True,
    interval_sec: int = 1800,
) -> CPAChannelRow:
    channel_id = str(uuid.uuid4())
    now = _now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cpa_channels (
                id, public_id, name, base_url, management_key, enabled,
                interval_sec, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                channel_id,
                str(uuid.uuid4()),
                name,
                base_url,
                encrypt_secret(management_key),
                int(enabled),
                max(300, int(interval_sec)),
                now,
                now,
            ),
        )
    channel = get_cpa_channel(channel_id)
    assert channel is not None
    return channel


def update_cpa_channel(channel_id: str, **fields: Any) -> CPAChannelRow | None:
    allowed = {"name", "base_url", "management_key", "enabled", "interval_sec"}
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        stored = conn.execute(
            "SELECT * FROM cpa_channels WHERE id = ?", (channel_id,)
        ).fetchone()
        if stored is None:
            return None
        current = CPAChannelRow.from_row(stored)
        changed: dict[str, Any] = {}
        for key, value in fields.items():
            if key not in allowed or value is None:
                continue
            normalized = value
            if key == "management_key":
                normalized = str(value)
            elif key == "enabled":
                normalized = bool(value)
            elif key == "interval_sec":
                normalized = max(300, int(value))
            if getattr(current, key) != normalized:
                changed[key] = normalized
        if not changed:
            return current
        updates: list[str] = []
        values: list[Any] = []
        for key, value in changed.items():
            if key == "management_key":
                value = encrypt_secret(str(value))
            elif key == "enabled":
                value = int(bool(value))
            updates.append(f"{key} = ?")
            values.append(value)
        if {"base_url", "management_key", "enabled"} & changed.keys():
            updates.append("collection_revision = collection_revision + 1")
        updates.append("updated_at = ?")
        values.extend((_now_iso(), channel_id))
        conn.execute(
            f"UPDATE cpa_channels SET {', '.join(updates)} WHERE id = ?", values
        )
    return get_cpa_channel(channel_id)


def delete_cpa_channel(channel_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM cpa_channels WHERE id = ?", (channel_id,))
        return cur.rowcount > 0


def mark_cpa_channel_due(channel_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE cpa_channels
            SET last_attempt_at = NULL,
                stale = CASE WHEN last_success_at IS NULL THEN 0 ELSE 1 END
            WHERE id = ?
            """,
            (channel_id,),
        )


def record_cpa_channel_attempt(
    channel_id: str,
    *,
    success: bool,
    error: str | None = None,
    attempted_at: str | None = None,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> None:
    now = attempted_at or _now_iso()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="cpa_channels",
            source_id=channel_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        if success:
            conn.execute(
                """
                UPDATE cpa_channels
                SET last_attempt_at = ?, last_success_at = ?,
                    last_attempt_status = 'success', stale = 0, error = NULL
                WHERE id = ?
                """,
                (now, now, channel_id),
            )
            return
        conn.execute(
            """
            UPDATE cpa_channels
            SET last_attempt_at = ?, last_attempt_status = 'error',
                stale = CASE WHEN last_success_at IS NULL THEN 0 ELSE 1 END,
                error = ?
            WHERE id = ?
            """,
            (now, error, channel_id),
        )
        conn.execute(
            """
            UPDATE cpa_quota_snapshots
            SET stale = CASE WHEN last_success_at IS NULL THEN 0 ELSE 1 END,
                updated_at = ?
            WHERE channel_id = ?
            """,
            (now, channel_id),
        )


def prepare_cpa_channel_discovery(
    channel_id: str,
    accounts: list[
        tuple[str, str | tuple[str, ...] | list[str] | None, str, str]
    ]
    | None = None,
    *,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> None:
    now = _now_iso()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="cpa_channels",
            source_id=channel_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        conn.execute(
            """
            UPDATE cpa_quota_snapshots
            SET visible = 0,
                stale = CASE WHEN last_success_at IS NULL THEN 0 ELSE 1 END,
                updated_at = ?
            WHERE channel_id = ?
            """,
            (now, channel_id),
        )
        for account_key_hash, legacy_values, account_display, plan in accounts or []:
            if isinstance(legacy_values, str):
                legacy_hashes = (legacy_values,)
            else:
                legacy_hashes = tuple(legacy_values or ())
            legacy_hashes = tuple(
                value
                for value in dict.fromkeys(legacy_hashes)
                if value and value != account_key_hash
            )
            current = conn.execute(
                """
                SELECT 1 FROM cpa_quota_snapshots
                WHERE channel_id = ? AND account_key_hash = ?
                """,
                (channel_id, account_key_hash),
            ).fetchone()
            if current is None:
                for legacy_hash in legacy_hashes:
                    cur = conn.execute(
                        """
                        UPDATE cpa_quota_snapshots
                        SET account_key_hash = ?
                        WHERE channel_id = ? AND account_key_hash = ?
                        """,
                        (account_key_hash, channel_id, legacy_hash),
                    )
                    if cur.rowcount:
                        current = True
                        break
            if current is not None:
                for legacy_hash in legacy_hashes:
                    conn.execute(
                        """
                        DELETE FROM cpa_quota_snapshots
                        WHERE channel_id = ? AND account_key_hash = ?
                        """,
                        (channel_id, legacy_hash),
                    )
            conn.execute(
                """
                UPDATE cpa_quota_snapshots
                SET account_display = ?, plan = ?,
                    visible = CASE
                        WHEN last_attempt_status IS NULL AND last_success_at IS NULL
                        THEN visible ELSE 1
                    END,
                    updated_at = ?
                WHERE channel_id = ? AND account_key_hash = ?
                """,
                (account_display, plan, now, channel_id, account_key_hash),
            )


def record_cpa_quota_snapshot(
    channel_id: str,
    account_key_hash: str,
    *,
    account_display: str,
    plan: str,
    success: bool,
    windows: list[dict[str, Any]] | None = None,
    error: str | None = None,
    attempted_at: str | None = None,
    quota_source: str | None = None,
    observed_at: str | None = None,
    active_attempted: bool = False,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> str:
    now = attempted_at or _now_iso()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="cpa_channels",
            source_id=channel_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        existing = conn.execute(
            """
            SELECT public_id, last_success_at
            FROM cpa_quota_snapshots
            WHERE channel_id = ? AND account_key_hash = ?
            """,
            (channel_id, account_key_hash),
        ).fetchone()
        public_id = existing["public_id"] if existing else str(uuid.uuid4())
        created_at = now if existing is None else None
        if success:
            conn.execute(
                """
                INSERT INTO cpa_quota_snapshots (
                    channel_id, account_key_hash, public_id, account_display, plan,
                    windows_json, visible, last_attempt_at, last_success_at,
                    last_attempt_status, stale, error, quota_source, observed_at,
                    last_active_attempt_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 'success', 0, NULL, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id, account_key_hash) DO UPDATE SET
                    account_display = excluded.account_display,
                    plan = excluded.plan,
                    windows_json = excluded.windows_json,
                    visible = 1,
                    last_attempt_at = excluded.last_attempt_at,
                    last_success_at = excluded.last_success_at,
                    last_attempt_status = 'success',
                    stale = 0,
                    error = NULL,
                    quota_source = COALESCE(excluded.quota_source, cpa_quota_snapshots.quota_source),
                    observed_at = COALESCE(excluded.observed_at, cpa_quota_snapshots.observed_at),
                    last_active_attempt_at = COALESCE(
                        excluded.last_active_attempt_at,
                        cpa_quota_snapshots.last_active_attempt_at
                    ),
                    updated_at = excluded.updated_at
                """,
                (
                    channel_id,
                    account_key_hash,
                    public_id,
                    account_display,
                    plan,
                    json.dumps(windows or [], ensure_ascii=False),
                    now,
                    now,
                    quota_source,
                    observed_at,
                    now if active_attempted else None,
                    created_at or now,
                    now,
                ),
            )
            return public_id
        conn.execute(
            """
            INSERT INTO cpa_quota_snapshots (
                channel_id, account_key_hash, public_id, account_display, plan,
                windows_json, visible, last_attempt_at, last_attempt_status,
                stale, error, quota_source, observed_at, last_active_attempt_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '[]', 1, ?, 'error', 0, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id, account_key_hash) DO UPDATE SET
                account_display = excluded.account_display,
                plan = excluded.plan,
                visible = 1,
                last_attempt_at = excluded.last_attempt_at,
                last_attempt_status = 'error',
                stale = CASE
                    WHEN cpa_quota_snapshots.last_success_at IS NULL THEN 0 ELSE 1
                END,
                error = excluded.error,
                quota_source = COALESCE(excluded.quota_source, cpa_quota_snapshots.quota_source),
                observed_at = COALESCE(excluded.observed_at, cpa_quota_snapshots.observed_at),
                last_active_attempt_at = COALESCE(
                    excluded.last_active_attempt_at,
                    cpa_quota_snapshots.last_active_attempt_at
                ),
                updated_at = excluded.updated_at
            """,
            (
                channel_id,
                account_key_hash,
                public_id,
                account_display,
                plan,
                now,
                error,
                quota_source,
                observed_at,
                now if active_attempted else None,
                created_at or now,
                now,
            ),
        )
        return public_id


def get_cpa_active_attempt(
    channel_id: str, account_key_hash: str
) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT last_active_attempt_at
            FROM cpa_quota_snapshots
            WHERE channel_id = ? AND account_key_hash = ?
            """,
            (channel_id, account_key_hash),
        ).fetchone()
    return row["last_active_attempt_at"] if row else None


def record_cpa_active_attempt(
    channel_id: str,
    account_key_hash: str,
    *,
    account_display: str,
    plan: str,
    attempted_at: str | None = None,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> str:
    now = attempted_at or _now_iso()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="cpa_channels",
            source_id=channel_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        existing = conn.execute(
            """
            SELECT public_id
            FROM cpa_quota_snapshots
            WHERE channel_id = ? AND account_key_hash = ?
            """,
            (channel_id, account_key_hash),
        ).fetchone()
        public_id = existing["public_id"] if existing else str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO cpa_quota_snapshots (
                channel_id, account_key_hash, public_id, account_display, plan,
                windows_json, visible, last_active_attempt_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '[]', 0, ?, ?, ?)
            ON CONFLICT(channel_id, account_key_hash) DO UPDATE SET
                account_display = excluded.account_display,
                plan = excluded.plan,
                last_active_attempt_at = excluded.last_active_attempt_at,
                updated_at = excluded.updated_at
            """,
            (
                channel_id,
                account_key_hash,
                public_id,
                account_display,
                plan,
                now,
                now,
                now,
            ),
        )
    return public_id


def list_cached_cpa_channels(*, enabled_only: bool = True) -> list[dict[str, Any]]:
    where = "WHERE c.enabled = 1" if enabled_only else ""
    with get_conn() as conn:
        channel_rows = conn.execute(
            f"SELECT * FROM cpa_channels c {where} ORDER BY c.created_at ASC"
        ).fetchall()
        snapshot_rows = conn.execute(
            """
            SELECT * FROM cpa_quota_snapshots
            WHERE visible = 1
            ORDER BY created_at ASC
            """
        ).fetchall()
    snapshots_by_channel: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot_rows:
        success = row["last_attempt_status"] == "success"
        item: dict[str, Any] = {
            "public_id": row["public_id"],
            "account": row["account_display"],
            "plan": row["plan"],
            "success": success,
            "stale": bool(row["stale"]),
            "updated_at": row["last_success_at"] or row["last_attempt_at"] or "",
            "last_attempt_at": row["last_attempt_at"],
            "windows": _decode_windows(row["windows_json"] or "[]"),
        }
        if row["quota_source"]:
            item["quota_source"] = row["quota_source"]
        if row["observed_at"]:
            item["observed_at"] = row["observed_at"]
        if not success:
            item["error"] = row["error"] or "等待首次采集"
        snapshots_by_channel.setdefault(row["channel_id"], []).append(item)

    result: list[dict[str, Any]] = []
    for row in channel_rows:
        success = row["last_attempt_status"] == "success"
        item = {
            "public_id": row["public_id"],
            "name": row["name"],
            "success": success,
            "stale": bool(row["stale"]),
            "last_attempt_at": row["last_attempt_at"],
            "last_success_at": row["last_success_at"],
            "accounts": snapshots_by_channel.get(row["id"], []),
        }
        if not success:
            item["error"] = row["error"] or "等待首次采集"
        if not enabled_only:
            item["id"] = row["id"]
            item["url"] = row["base_url"]
            item["enabled"] = bool(row["enabled"])
            item["interval_sec"] = max(300, int(row["interval_sec"]))
            item["created_at"] = row["created_at"]
            item["updated_at"] = row["updated_at"]
        result.append(item)
    return result


def insert_usage_records_ignore(
    account_id: str,
    workspace_id: str,
    records: list[dict[str, Any]],
    *,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> int:
    if not records:
        return 0
    synced_at = _now_iso()
    inserted = 0
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="opencode_accounts",
            source_id=account_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        for rec in records:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO usage_records (
                    usg_id, account_id, workspace_id, created_at, model, provider,
                    input_tokens, output_tokens, cost_raw, cost_usd, key_id, plan, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec["usg_id"],
                    account_id,
                    workspace_id,
                    rec["created_at"],
                    rec["model"],
                    rec.get("provider"),
                    rec["input_tokens"],
                    rec["output_tokens"],
                    rec["cost_raw"],
                    rec["cost_usd"],
                    rec.get("key_id"),
                    rec.get("plan"),
                    synced_at,
                ),
            )
            inserted += cur.rowcount
    return inserted


def list_usage_records(
    account_id: str,
    *,
    offset: int = 0,
    limit: int = 50,
    key_id: str | None = None,
) -> tuple[list[UsageRecordRow], int]:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    where = "WHERE account_id = ?"
    params: list[Any] = [account_id]
    if key_id:
        where += " AND key_id = ?"
        params.append(key_id)
    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM usage_records {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM usage_records {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    records = [
        UsageRecordRow(
            usg_id=r["usg_id"],
            account_id=r["account_id"],
            workspace_id=r["workspace_id"],
            created_at=r["created_at"],
            model=r["model"],
            provider=r["provider"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            cost_raw=r["cost_raw"],
            cost_usd=r["cost_usd"],
            key_id=r["key_id"],
            plan=r["plan"],
            synced_at=r["synced_at"],
        )
        for r in rows
    ]
    return records, int(total)


def list_usage_key_ids(account_id: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT key_id FROM usage_records
            WHERE account_id = ? AND key_id IS NOT NULL AND key_id != ''
            ORDER BY key_id
            """,
            (account_id,),
        ).fetchall()
    return [r["key_id"] for r in rows]


def list_all_usage_records(
    *,
    offset: int = 0,
    limit: int = 50,
    account_id: str | None = None,
) -> tuple[list[UsageRecordWithAccount], int]:
    offset = max(0, offset)
    limit = max(1, min(limit, 200))
    where = ""
    params: list[Any] = []
    if account_id:
        where = "WHERE ur.account_id = ?"
        params.append(account_id)
    with get_conn() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM usage_records ur
            JOIN opencode_accounts oa ON oa.id = ur.account_id
            {where}
            """,
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT ur.*, oa.name AS account_name
            FROM usage_records ur
            JOIN opencode_accounts oa ON oa.id = ur.account_id
            {where}
            ORDER BY ur.created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
    records = [
        UsageRecordWithAccount(
            usg_id=r["usg_id"],
            account_id=r["account_id"],
            workspace_id=r["workspace_id"],
            created_at=r["created_at"],
            model=r["model"],
            provider=r["provider"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            cost_raw=r["cost_raw"],
            cost_usd=r["cost_usd"],
            key_id=r["key_id"],
            plan=r["plan"],
            synced_at=r["synced_at"],
            account_name=r["account_name"],
        )
        for r in rows
    ]
    return records, int(total)


def opencode_daily_stats(days: int = 30) -> list[dict[str, Any]]:
    days = max(1, min(days, 365))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS date,
                   SUM(cost_usd) AS total_cost_usd,
                   COUNT(*) AS request_count
            FROM usage_records
            WHERE substr(created_at, 1, 10) >= date('now', ?)
            GROUP BY substr(created_at, 1, 10)
            ORDER BY date DESC
            """,
            (f"-{days} days",),
        ).fetchall()
    return [
        {
            "date": r["date"],
            "total_cost_usd": round(float(r["total_cost_usd"] or 0), 6),
            "request_count": int(r["request_count"]),
        }
        for r in rows
    ]


def opencode_daily_model_stats(days: int = 30) -> list[dict[str, Any]]:
    days = max(1, min(days, 365))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS date,
                   model,
                   SUM(cost_usd) AS total_cost_usd,
                   COUNT(*) AS request_count
            FROM usage_records
            WHERE substr(created_at, 1, 10) >= date('now', ?)
            GROUP BY substr(created_at, 1, 10), model
            ORDER BY date ASC, model ASC
            """,
            (f"-{days} days",),
        ).fetchall()
    return [
        {
            "date": r["date"],
            "model": r["model"],
            "total_cost_usd": round(float(r["total_cost_usd"] or 0), 6),
            "request_count": int(r["request_count"]),
        }
        for r in rows
    ]


def get_usage_sync_state(account_id: str) -> UsageSyncStateRow:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM usage_sync_state WHERE account_id = ?", (account_id,)
        ).fetchone()
    return UsageSyncStateRow.from_row(row, account_id)


def update_usage_sync_state(
    account_id: str,
    *,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
    **fields: Any,
) -> None:
    allowed = {
        "last_sync_at",
        "last_sync_status",
        "last_sync_error",
        "last_inserted_count",
        "deepest_page_fetched",
        "total_records",
        "oldest_record_at",
        "newest_record_at",
    }
    updates: list[str] = []
    values: list[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        updates.append(f"{key} = ?")
        values.append(value)
    if not updates:
        return
    values.append(account_id)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="opencode_accounts",
            source_id=account_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        conn.execute(
            f"UPDATE usage_sync_state SET {', '.join(updates)} WHERE account_id = ?",
            values,
        )


def refresh_usage_sync_totals(
    account_id: str,
    *,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table="opencode_accounts",
            source_id=account_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   MIN(created_at) AS oldest,
                   MAX(created_at) AS newest
            FROM usage_records WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
        conn.execute(
            """
            UPDATE usage_sync_state
            SET total_records = ?, oldest_record_at = ?, newest_record_at = ?
            WHERE account_id = ?
            """,
            (row["total"], row["oldest"], row["newest"], account_id),
        )


def has_service_settings() -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM service_settings WHERE id = 1").fetchone()
    return row is not None


def get_service_settings_payload() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute("SELECT payload FROM service_settings WHERE id = 1").fetchone()
    if row is None:
        return {}
    try:
        data = json.loads(row["payload"])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_service_settings_payload(payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO service_settings (id, payload, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (json.dumps(payload, ensure_ascii=False), _now_iso()),
        )


def count_opencode_accounts() -> int:
    with get_conn() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM opencode_accounts").fetchone()[0])


def count_ollama_accounts() -> int:
    with get_conn() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM ollama_accounts").fetchone()[0])


def count_cpa_channels() -> int:
    with get_conn() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM cpa_channels").fetchone()[0])


def _compact_database_after_secret_migration() -> None:
    conn = sqlite3.connect(db_path())
    try:
        conn.execute("PRAGMA secure_delete = ON")
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        if journal_mode == "wal":
            checkpoint = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint is not None and int(checkpoint[0]) != 0:
                raise sqlite3.OperationalError("database is busy during secure rewrite")
        conn.execute("VACUUM")
        if journal_mode == "wal":
            checkpoint = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint is not None and int(checkpoint[0]) != 0:
                raise sqlite3.OperationalError("database is busy during secure rewrite")
    finally:
        conn.close()


def migrate_account_secrets() -> None:
    migrated = False
    with get_conn() as conn:
        conn.execute("PRAGMA secure_delete = ON")
        for table, column in (
            ("opencode_accounts", "auth_cookie"),
            ("ollama_accounts", "session_cookie"),
            ("cpa_channels", "management_key"),
        ):
            rows = conn.execute(f"SELECT id, {column} FROM {table}").fetchall()
            for row in rows:
                stored = str(row[column])
                encrypted = stored if is_encrypted(stored) else encrypt_secret(stored)
                decrypt_secret(encrypted)
                if encrypted != stored:
                    conn.execute(
                        f"UPDATE {table} SET {column} = ? WHERE id = ?",
                        (encrypted, row["id"]),
                    )
                    migrated = True
    if migrated:
        _compact_database_after_secret_migration()


def sync_admin_token_fingerprint(fingerprint: str) -> bool:
    """Persist the current token fingerprint and revoke sessions after rotation."""
    now = _now_iso()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM security_state WHERE key = 'admin_token_fingerprint'"
        ).fetchone()
        if row is not None and row["value"] == fingerprint:
            return False
        conn.execute("DELETE FROM admin_sessions")
        conn.execute(
            """
            INSERT INTO security_state (key, value, updated_at)
            VALUES ('admin_token_fingerprint', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (fingerprint, now),
        )
        return True


def apply_admin_login_attempt(
    source_hmac: str,
    *,
    success: bool,
    cutoff_iso: str,
    attempted_at: str | None = None,
    max_failures: int = 5,
) -> tuple[bool, int]:
    """Atomically enforce the login window and record or clear one attempt."""
    if max_failures < 1:
        raise ValueError("max_failures must be positive")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM admin_login_attempts WHERE failed_at <= ?", (cutoff_iso,)
        )
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM admin_login_attempts
            WHERE source_hmac = ? AND failed_at > ?
            """,
            (source_hmac, cutoff_iso),
        ).fetchone()
        failure_count = int(row[0])
        if failure_count >= max_failures:
            return False, failure_count
        if success:
            conn.execute(
                "DELETE FROM admin_login_attempts WHERE source_hmac = ?", (source_hmac,)
            )
            return True, 0
        conn.execute(
            "INSERT INTO admin_login_attempts (source_hmac, failed_at) VALUES (?, ?)",
            (source_hmac, attempted_at or _now_iso()),
        )
        return True, failure_count + 1


def acquire_scheduler_lease(
    name: str,
    owner_id: str,
    *,
    ttl_sec: int = 120,
    now: datetime | None = None,
) -> bool:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    current_iso = current.isoformat().replace("+00:00", "Z")
    expires_iso = (current + timedelta(seconds=ttl_sec)).isoformat().replace(
        "+00:00", "Z"
    )
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO scheduler_leases (name, owner_id, expires_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                owner_id = excluded.owner_id,
                expires_at = excluded.expires_at,
                updated_at = excluded.updated_at
            WHERE scheduler_leases.owner_id = excluded.owner_id
               OR scheduler_leases.expires_at <= ?
            """,
            (name, owner_id, expires_iso, current_iso, current_iso),
        )
        return cur.rowcount > 0


def renew_scheduler_lease(
    name: str,
    owner_id: str,
    *,
    ttl_sec: int = 120,
    now: datetime | None = None,
) -> bool:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    current_iso = current.isoformat().replace("+00:00", "Z")
    expires_iso = (current + timedelta(seconds=ttl_sec)).isoformat().replace(
        "+00:00", "Z"
    )
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE scheduler_leases
            SET expires_at = ?, updated_at = ?
            WHERE name = ? AND owner_id = ? AND expires_at > ?
            """,
            (expires_iso, current_iso, name, owner_id, current_iso),
        )
        return cur.rowcount > 0


def holds_scheduler_lease(
    name: str, owner_id: str, *, now: datetime | None = None
) -> bool:
    current_iso = (now or datetime.now(UTC)).astimezone(UTC).isoformat().replace(
        "+00:00", "Z"
    )
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM scheduler_leases
            WHERE name = ? AND owner_id = ? AND expires_at > ?
            """,
            (name, owner_id, current_iso),
        ).fetchone()
    return row is not None


def release_scheduler_lease(name: str, owner_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM scheduler_leases WHERE name = ? AND owner_id = ?",
            (name, owner_id),
        )
        return cur.rowcount > 0


@dataclass
class AdminSessionRow:
    token_hash: str
    created_at: str
    expires_at: str
    last_used_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> AdminSessionRow:
        return cls(
            token_hash=row["token_hash"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_used_at=row["last_used_at"],
        )


def create_admin_session(token_hash: str, expires_at: str) -> AdminSessionRow:
    now = _now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO admin_sessions (token_hash, created_at, expires_at, last_used_at)
            VALUES (?, ?, ?, ?)
            """,
            (token_hash, now, expires_at, now),
        )
    session = get_admin_session(token_hash)
    assert session is not None
    return session


def get_admin_session(token_hash: str) -> AdminSessionRow | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM admin_sessions WHERE token_hash = ?", (token_hash,)
        ).fetchone()
    return AdminSessionRow.from_row(row) if row else None


def touch_admin_session(token_hash: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE admin_sessions SET last_used_at = ? WHERE token_hash = ?",
            (_now_iso(), token_hash),
        )


def delete_admin_session(token_hash: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM admin_sessions WHERE token_hash = ?", (token_hash,)
        )
        return cur.rowcount > 0


def purge_expired_admin_sessions(now_iso: str | None = None) -> int:
    cutoff = now_iso or _now_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM admin_sessions WHERE expires_at <= ?", (cutoff,)
        )
        return cur.rowcount


def _decode_windows(raw: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _record_quota_snapshot(
    *,
    table: str,
    account_id: str,
    success: bool,
    windows: list[dict[str, Any]] | None,
    error: str | None,
    plan: str | None = None,
    attempted_at: str | None = None,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> None:
    now = attempted_at or _now_iso()
    source_table = {
        "opencode_quota_snapshots": "opencode_accounts",
        "ollama_quota_snapshots": "ollama_accounts",
    }[table]
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _validate_collection_guard(
            conn,
            source_table=source_table,
            source_id=account_id,
            expected_collection_revision=expected_collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        existing = conn.execute(
            f"SELECT public_id, last_success_at FROM {table} WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        public_id = existing["public_id"] if existing else str(uuid.uuid4())
        if success:
            if table == "ollama_quota_snapshots":
                conn.execute(
                    """
                    INSERT INTO ollama_quota_snapshots (
                        account_id, public_id, plan, windows_json, last_attempt_at,
                        last_success_at, last_attempt_status, stale, error
                    ) VALUES (?, ?, ?, ?, ?, ?, 'success', 0, NULL)
                    ON CONFLICT(account_id) DO UPDATE SET
                        plan = excluded.plan,
                        windows_json = excluded.windows_json,
                        last_attempt_at = excluded.last_attempt_at,
                        last_success_at = excluded.last_success_at,
                        last_attempt_status = 'success', stale = 0, error = NULL
                    """,
                    (account_id, public_id, plan, json.dumps(windows or []), now, now),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO opencode_quota_snapshots (
                        account_id, public_id, windows_json, last_attempt_at,
                        last_success_at, last_attempt_status, stale, error
                    ) VALUES (?, ?, ?, ?, ?, 'success', 0, NULL)
                    ON CONFLICT(account_id) DO UPDATE SET
                        windows_json = excluded.windows_json,
                        last_attempt_at = excluded.last_attempt_at,
                        last_success_at = excluded.last_success_at,
                        last_attempt_status = 'success', stale = 0, error = NULL
                    """,
                    (account_id, public_id, json.dumps(windows or []), now, now),
                )
            return

        if existing is None:
            if table == "ollama_quota_snapshots":
                conn.execute(
                    """
                    INSERT INTO ollama_quota_snapshots (
                        account_id, public_id, plan, windows_json, last_attempt_at,
                        last_attempt_status, stale, error
                    ) VALUES (?, ?, ?, '[]', ?, 'error', 0, ?)
                    """,
                    (account_id, public_id, plan, now, error),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO opencode_quota_snapshots (
                        account_id, public_id, windows_json, last_attempt_at,
                        last_attempt_status, stale, error
                    ) VALUES (?, ?, '[]', ?, 'error', 0, ?)
                    """,
                    (account_id, public_id, now, error),
                )
        else:
            conn.execute(
                f"""
                UPDATE {table}
                SET last_attempt_at = ?, last_attempt_status = 'error',
                    stale = CASE WHEN last_success_at IS NULL THEN 0 ELSE 1 END,
                    error = ?
                WHERE account_id = ?
                """,
                (now, error, account_id),
            )


def record_opencode_quota_snapshot(
    account_id: str,
    *,
    success: bool,
    windows: list[dict[str, Any]] | None = None,
    error: str | None = None,
    attempted_at: str | None = None,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> None:
    _record_quota_snapshot(
        table="opencode_quota_snapshots",
        account_id=account_id,
        success=success,
        windows=windows,
        error=error,
        attempted_at=attempted_at,
        expected_collection_revision=expected_collection_revision,
        lease_name=lease_name,
        lease_owner_id=lease_owner_id,
    )


def record_ollama_quota_snapshot(
    account_id: str,
    *,
    success: bool,
    plan: str | None = None,
    windows: list[dict[str, Any]] | None = None,
    error: str | None = None,
    attempted_at: str | None = None,
    expected_collection_revision: int | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> None:
    _record_quota_snapshot(
        table="ollama_quota_snapshots",
        account_id=account_id,
        success=success,
        plan=plan,
        windows=windows,
        error=error,
        attempted_at=attempted_at,
        expected_collection_revision=expected_collection_revision,
        lease_name=lease_name,
        lease_owner_id=lease_owner_id,
    )


def get_quota_snapshot_attempt(provider: str, account_id: str) -> str | None:
    table = {
        "opencode": "opencode_quota_snapshots",
        "ollama": "ollama_quota_snapshots",
    }.get(provider)
    if table is None:
        raise ValueError(f"unsupported quota provider: {provider}")
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT last_attempt_at FROM {table} WHERE account_id = ?", (account_id,)
        ).fetchone()
    return row["last_attempt_at"] if row else None


def mark_quota_snapshot_due(provider: str, account_id: str) -> None:
    table = {
        "opencode": "opencode_quota_snapshots",
        "ollama": "ollama_quota_snapshots",
    }.get(provider)
    if table is None:
        raise ValueError(f"unsupported quota provider: {provider}")
    with get_conn() as conn:
        conn.execute(
            f"""
            UPDATE {table}
            SET last_attempt_at = NULL,
                stale = CASE WHEN last_success_at IS NULL THEN 0 ELSE 1 END
            WHERE account_id = ?
            """,
            (account_id,),
        )


def _list_cached_quota(provider: str, *, enabled_only: bool) -> list[dict[str, Any]]:
    if provider == "opencode":
        account_table = "opencode_accounts"
        snapshot_table = "opencode_quota_snapshots"
        plan_select = "NULL AS plan"
    elif provider == "ollama":
        account_table = "ollama_accounts"
        snapshot_table = "ollama_quota_snapshots"
        plan_select = "qs.plan AS plan"
    else:
        raise ValueError(f"unsupported quota provider: {provider}")
    where = "WHERE a.enabled = 1" if enabled_only else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT a.id AS internal_id, a.name, a.enabled,
                   qs.public_id, qs.windows_json, qs.last_attempt_at,
                   qs.last_success_at, qs.last_attempt_status, qs.stale, qs.error,
                   {plan_select}
            FROM {account_table} a
            LEFT JOIN {snapshot_table} qs ON qs.account_id = a.id
            {where}
            ORDER BY a.created_at ASC
            """
        ).fetchall()
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        success = row["last_attempt_status"] == "success"
        item: dict[str, Any] = {
            "index": index,
            "public_id": row["public_id"],
            "name": row["name"],
            "success": success,
            "stale": bool(row["stale"]),
            "updated_at": row["last_success_at"] or row["last_attempt_at"] or "",
            "last_attempt_at": row["last_attempt_at"],
            "windows": _decode_windows(row["windows_json"] or "[]"),
        }
        if not success:
            item["error"] = row["error"] or "等待首次采集"
        if provider == "ollama" and row["plan"]:
            item["plan"] = row["plan"]
        if not enabled_only:
            item["account_id"] = row["internal_id"]
            item["enabled"] = bool(row["enabled"])
        result.append(item)
    return result


def list_cached_opencode_quotas(*, enabled_only: bool = True) -> list[dict[str, Any]]:
    return _list_cached_quota("opencode", enabled_only=enabled_only)


def list_cached_ollama_quotas(*, enabled_only: bool = True) -> list[dict[str, Any]]:
    return _list_cached_quota("ollama", enabled_only=enabled_only)


def get_cached_opencode_quota(account_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in list_cached_opencode_quotas(enabled_only=False)
            if item.get("account_id") == account_id
        ),
        None,
    )


def get_cached_ollama_quota(account_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in list_cached_ollama_quotas(enabled_only=False)
            if item.get("account_id") == account_id
        ),
        None,
    )
