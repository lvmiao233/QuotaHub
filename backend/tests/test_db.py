import sqlite3
import threading
from datetime import UTC, datetime

import pytest

from app import db
from app.bootstrap import ensure_bootstrapped
from app.secrets import encrypt_secret


def test_create_and_list_opencode_account(temp_data_dir):
    row = db.create_opencode_account(
        name="test",
        workspace_id="Default",
        auth_cookie="auth=token",
    )
    accounts = db.list_opencode_accounts()
    assert len(accounts) == 1
    assert accounts[0].id == row.id
    assert accounts[0].name == "test"


def test_insert_usage_records_ignore(temp_data_dir):
    account = db.create_opencode_account(
        name="test",
        workspace_id="Default",
        auth_cookie="auth=token",
    )
    records = [
        {
            "usg_id": "usg_001",
            "created_at": "2026-07-09T08:16:06.000Z",
            "model": "glm-5.2",
            "provider": "deepinfra-glm-5.2",
            "input_tokens": 100,
            "output_tokens": 10,
            "cost_raw": 1000,
            "cost_usd": 0.000001,
            "key_id": "key_abc",
            "plan": "lite",
        }
    ]
    inserted = db.insert_usage_records_ignore(account.id, "wrk_test", records)
    assert inserted == 1
    inserted_again = db.insert_usage_records_ignore(account.id, "wrk_test", records)
    assert inserted_again == 0

    listed, total = db.list_usage_records(account.id)
    assert total == 1
    assert listed[0].usg_id == "usg_001"


def test_list_all_usage_records_and_daily_stats(temp_data_dir):
    today = datetime.now(UTC).date().isoformat()
    account_a = db.create_opencode_account(
        name="Alpha",
        workspace_id="Default",
        auth_cookie="auth=a",
    )
    account_b = db.create_opencode_account(
        name="Beta",
        workspace_id="Default",
        auth_cookie="auth=b",
    )
    db.insert_usage_records_ignore(
        account_a.id,
        "wrk_a",
        [
            {
                "usg_id": "usg_a1",
                "created_at": f"{today}T10:00:00.000Z",
                "model": "glm-5.2",
                "provider": "p",
                "input_tokens": 1,
                "output_tokens": 1,
                "cost_raw": 1000,
                "cost_usd": 0.01,
                "key_id": "k1",
                "plan": "lite",
            }
        ],
    )
    db.insert_usage_records_ignore(
        account_b.id,
        "wrk_b",
        [
            {
                "usg_id": "usg_b1",
                "created_at": f"{today}T12:00:00.000Z",
                "model": "gpt",
                "provider": "p",
                "input_tokens": 2,
                "output_tokens": 2,
                "cost_raw": 2000,
                "cost_usd": 0.02,
                "key_id": "k2",
                "plan": "lite",
            }
        ],
    )

    records, total = db.list_all_usage_records(limit=10)
    assert total == 2
    assert {r.account_name for r in records} == {"Alpha", "Beta"}

    filtered, filtered_total = db.list_all_usage_records(account_id=account_a.id)
    assert filtered_total == 1
    assert filtered[0].account_name == "Alpha"

    stats = db.opencode_daily_stats(days=30)
    assert len(stats) >= 1
    assert stats[0]["request_count"] >= 1

    model_stats = db.opencode_daily_model_stats(days=30)
    assert len(model_stats) >= 1
    assert model_stats[0]["model"]


def test_import_from_config_once(temp_data_dir, monkeypatch: pytest.MonkeyPatch):
    config = temp_data_dir / "config.json"
    monkeypatch.setenv("QUOTAHUB_CONFIG", str(config))
    config.write_text(
        """
        {
          "listen_host": "127.0.0.1",
          "listen_port": 8788,
          "opencode_accounts": [
            {
              "name": "Imported",
              "workspace_id": "Default",
              "auth_cookie": "auth=imported"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    ensure_bootstrapped()
    assert db.count_opencode_accounts() == 1
    assert db.imported_flag_path().exists()

    config.write_text(
        '{"listen_host":"127.0.0.1","listen_port":8788,"opencode_accounts":[]}',
        encoding="utf-8",
    )
    ensure_bootstrapped()
    assert db.count_opencode_accounts() == 1


def test_init_db_backfills_stable_public_ids_for_legacy_accounts(temp_data_dir):
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO opencode_accounts (
                id, name, workspace_id, auth_cookie, created_at, updated_at
            ) VALUES ('legacy-open', 'Legacy Open', 'Default', 'ciphertext-placeholder', ?, ?)
            """,
            (now, now),
        )
        conn.execute(
            """
            INSERT INTO ollama_accounts (
                id, name, session_cookie, created_at, updated_at
            ) VALUES ('legacy-ollama', 'Legacy Ollama', 'ciphertext-placeholder', ?, ?)
            """,
            (now, now),
        )

    db.init_db()
    with db.get_conn() as conn:
        first = (
            conn.execute(
                "SELECT public_id FROM opencode_quota_snapshots WHERE account_id = 'legacy-open'"
            ).fetchone()[0],
            conn.execute(
                "SELECT public_id FROM ollama_quota_snapshots WHERE account_id = 'legacy-ollama'"
            ).fetchone()[0],
        )

    db.init_db()
    with db.get_conn() as conn:
        second = (
            conn.execute(
                "SELECT public_id FROM opencode_quota_snapshots WHERE account_id = 'legacy-open'"
            ).fetchone()[0],
            conn.execute(
                "SELECT public_id FROM ollama_quota_snapshots WHERE account_id = 'legacy-ollama'"
            ).fetchone()[0],
        )
    assert first == second


def test_init_db_migrates_cpa_passive_snapshot_columns_idempotently(temp_data_dir):
    with db.get_conn() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(cpa_quota_snapshots)").fetchall()
        }
    assert {"quota_source", "observed_at", "last_active_attempt_at"} <= columns

    db.init_db()
    with db.get_conn() as conn:
        columns_after = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(cpa_quota_snapshots)").fetchall()
        }
    assert columns_after == columns


def test_import_from_config_preserves_disabled_accounts(temp_data_dir, monkeypatch):
    config = temp_data_dir / "legacy-disabled.json"
    monkeypatch.setenv("QUOTAHUB_CONFIG", str(config))
    config.write_text(
        '''{
          "opencode_accounts": [{
            "name": "Disabled Open", "workspace_id": "Default",
            "auth_cookie": "auth=disabled", "enabled": false
          }],
          "ollama_accounts": [{
            "name": "Disabled Ollama", "session_cookie": "aid=x", "enabled": false
          }]
        }''',
        encoding="utf-8",
    )

    ensure_bootstrapped()

    assert db.list_opencode_accounts()[0].enabled is False
    assert db.list_ollama_accounts()[0].enabled is False


def test_collection_revision_changes_only_for_collection_inputs(temp_data_dir):
    opencode = db.create_opencode_account(
        name="Open", workspace_id="Default", auth_cookie="auth=old"
    )
    db.record_opencode_resolved_workspace(
        opencode.id,
        "wrk_old",
        expected_collection_revision=opencode.collection_revision,
    )
    renamed = db.update_opencode_account(
        opencode.id, name="Renamed", show_weekly=False
    )
    assert renamed.collection_revision == opencode.collection_revision
    assert renamed.resolved_workspace_id == "wrk_old"

    credential_changed = db.update_opencode_account(
        opencode.id, auth_cookie="auth=new"
    )
    assert credential_changed.collection_revision == opencode.collection_revision + 1
    assert credential_changed.resolved_workspace_id is None
    workspace_changed = db.update_opencode_account(
        opencode.id, workspace_id="Another"
    )
    assert workspace_changed.collection_revision == credential_changed.collection_revision + 1
    disabled = db.update_opencode_account(opencode.id, enabled=False)
    assert disabled.collection_revision == workspace_changed.collection_revision + 1

    ollama = db.create_ollama_account(name="Ollama", session_cookie="session=old")
    displayed = db.update_ollama_account(ollama.id, name="Shown", show_weekly=False)
    assert displayed.collection_revision == ollama.collection_revision
    cookie_changed = db.update_ollama_account(ollama.id, session_cookie="session=new")
    assert cookie_changed.collection_revision == ollama.collection_revision + 1

    channel = db.create_cpa_channel(
        name="CPA", base_url="https://cpa.example.test", management_key="old-key"
    )
    display_changed = db.update_cpa_channel(
        channel.id, name="Renamed CPA", interval_sec=3600
    )
    assert display_changed.collection_revision == channel.collection_revision
    key_changed = db.update_cpa_channel(channel.id, management_key="new-key")
    assert key_changed.collection_revision == channel.collection_revision + 1


def test_init_db_adds_collection_revision_to_legacy_tables(temp_data_dir):
    db.db_path().unlink()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    with sqlite3.connect(db.db_path()) as conn:
        conn.executescript(
            """
            CREATE TABLE opencode_accounts (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, workspace_id TEXT NOT NULL,
                resolved_workspace_id TEXT, auth_cookie TEXT NOT NULL,
                show_rolling INTEGER NOT NULL DEFAULT 1,
                show_weekly INTEGER NOT NULL DEFAULT 1,
                show_monthly INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE ollama_accounts (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, session_cookie TEXT NOT NULL,
                show_session INTEGER NOT NULL DEFAULT 1,
                show_weekly INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE cpa_channels (
                id TEXT PRIMARY KEY, public_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, base_url TEXT NOT NULL,
                management_key TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
                interval_sec INTEGER NOT NULL DEFAULT 1800,
                last_attempt_at TEXT, last_success_at TEXT,
                last_attempt_status TEXT, stale INTEGER NOT NULL DEFAULT 0,
                error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO opencode_accounts (
                id, name, workspace_id, auth_cookie, created_at, updated_at
            ) VALUES ('legacy-open', 'Legacy', 'Default', ?, ?, ?)
            """,
            (encrypt_secret("auth=legacy"), now, now),
        )
    db.init_db()
    db.init_db()

    with db.get_conn() as conn:
        for table in ("opencode_accounts", "ollama_accounts", "cpa_channels"):
            columns = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            assert "collection_revision" in columns
        revision = conn.execute(
            "SELECT collection_revision FROM opencode_accounts WHERE id = 'legacy-open'"
        ).fetchone()[0]
    assert revision == 1


def test_guarded_usage_write_rejects_revision_changed_by_other_connection(
    temp_data_dir,
):
    account = db.create_opencode_account(
        name="Race", workspace_id="Default", auth_cookie="auth=old"
    )
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []
    record = {
        "usg_id": "usg-race",
        "created_at": "2026-08-14T00:00:00Z",
        "model": "model",
        "provider": "provider",
        "input_tokens": 1,
        "output_tokens": 1,
        "cost_raw": 1,
        "cost_usd": 0.0,
    }

    def write_stale_page() -> None:
        barrier.wait()
        try:
            db.insert_usage_records_ignore(
                account.id,
                "wrk_old",
                [record],
                expected_collection_revision=account.collection_revision,
            )
        except BaseException as exc:  # noqa: BLE001 - captured from worker thread
            errors.append(exc)

    conn = sqlite3.connect(db.db_path(), timeout=5)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE opencode_accounts
            SET auth_cookie = ?, collection_revision = collection_revision + 1
            WHERE id = ?
            """,
            (encrypt_secret("auth=new"), account.id),
        )
        worker = threading.Thread(target=write_stale_page)
        worker.start()
        barrier.wait()
        conn.commit()
        worker.join(timeout=5)
    finally:
        conn.close()

    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], db.CollectionGuardRejected)
    assert errors[0].reason == "source_changed"
    assert db.list_usage_records(account.id)[1] == 0


def test_guarded_quota_write_rejects_expired_owner_lease(temp_data_dir):
    account = db.create_opencode_account(
        name="Lease", workspace_id="Default", auth_cookie="auth=lease"
    )
    assert db.acquire_scheduler_lease("quota-test", "owner-a") is True
    with db.get_conn() as conn:
        conn.execute(
            "DELETE FROM scheduler_leases WHERE name = ?", ("quota-test",)
        )

    with pytest.raises(db.CollectionGuardRejected) as exc_info:
        db.record_opencode_quota_snapshot(
            account.id,
            success=True,
            windows=[],
            expected_collection_revision=account.collection_revision,
            lease_name="quota-test",
            lease_owner_id="owner-a",
        )
    assert exc_info.value.reason == "lease_lost"
    assert db.get_quota_snapshot_attempt("opencode", account.id) is None
