from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import load_service_config, merge_settings_with_defaults, save_settings_payload
from app.main import app
from app.quota import LABEL_ROLLING, QuotaAccount, QuotaWindow
from app.quota_sync import (
    QuotaCollectionInterrupted,
    collect_due_quotas,
    collect_opencode_account,
)


def _window(*, used: float = 10.0) -> dict[str, object]:
    return {
        "label": LABEL_ROLLING,
        "used": used,
        "remaining": 100.0 - used,
        "total": 100.0,
        "unit": "%",
        "reset_at": "2026-08-11T12:00:00Z",
        "reset_in_sec": 3600,
    }


def test_snapshot_failure_preserves_last_success_and_disabled_accounts_are_hidden(temp_data_dir):
    account = db.create_opencode_account(
        name="Cached",
        workspace_id="Default",
        auth_cookie="auth=secret",
    )
    db.record_opencode_quota_snapshot(
        account.id,
        success=True,
        windows=[_window()],
        attempted_at="2026-08-11T08:00:00Z",
    )
    first = db.get_cached_opencode_quota(account.id)
    assert first is not None
    public_id = first["public_id"]

    db.record_opencode_quota_snapshot(
        account.id,
        success=False,
        error="额度采集失败",
        attempted_at="2026-08-11T09:00:00Z",
    )
    failed = db.get_cached_opencode_quota(account.id)
    assert failed is not None
    assert failed["public_id"] == public_id
    assert failed["success"] is False
    assert failed["stale"] is True
    assert failed["windows"] == [_window()]
    assert failed["updated_at"] == "2026-08-11T08:00:00Z"

    db.update_opencode_account(account.id, enabled=False)
    assert db.list_cached_opencode_quotas() == []
    assert db.get_cached_opencode_quota(account.id) is not None


def test_public_quota_and_overview_are_snapshot_only(temp_data_dir):
    account = db.create_opencode_account(
        name="Cached",
        workspace_id="Default",
        auth_cookie="auth=secret",
    )
    db.record_opencode_quota_snapshot(account.id, success=True, windows=[_window()])

    client = TestClient(app)
    with (
        patch("app.quota.fetch_quota_for_account", side_effect=AssertionError("network")),
        patch("app.ollama_quota.fetch_ollama_quota_for_account", side_effect=AssertionError("network")),
    ):
        quota_response = client.get("/api/public/quota")
        overview_response = client.get("/api/public/overview")

    assert quota_response.status_code == 200
    item = quota_response.json()["opencode"][0]
    assert item["name"] == "Cached"
    assert item["public_id"]
    assert "account_id" not in item
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["opencode"]["account_count"] == 1
    assert overview["opencode"]["accounts"][0]["public_id"] == item["public_id"]
    assert "account_id" not in overview["opencode"]["accounts"][0]


@pytest.mark.asyncio
async def test_scheduler_collects_due_account_once_and_uses_snapshot(temp_data_dir):
    account = db.create_opencode_account(
        name="Due",
        workspace_id="Default",
        auth_cookie="auth=secret",
    )
    result = QuotaAccount(
        index=0,
        name="Due",
        workspace_id="wrk_due",
        success=True,
        updated_at="2026-08-11T08:00:00Z",
        windows=[
            QuotaWindow(
                label=LABEL_ROLLING,
                used=10,
                remaining=90,
                total=100,
                unit="%",
                reset_at="2026-08-11T12:00:00Z",
                reset_in_sec=3600,
            )
        ],
    )
    fetch = AsyncMock(return_value=result)
    with patch("app.quota_sync.fetch_quota_for_account", fetch):
        await collect_due_quotas()
        await collect_due_quotas()

    fetch.assert_awaited_once()
    cached = db.get_cached_opencode_quota(account.id)
    assert cached is not None
    assert cached["success"] is True
    assert cached["windows"][0]["remaining"] == 90


@pytest.mark.asyncio
async def test_scheduler_discards_result_after_credential_change(temp_data_dir):
    account = db.create_opencode_account(
        name="Changing",
        workspace_id="Default",
        auth_cookie="auth=old",
    )

    async def change_credential(*_args, **_kwargs):
        db.update_opencode_account(account.id, auth_cookie="auth=new")
        return QuotaAccount(
            index=0,
            name="Changing",
            workspace_id="wrk_old",
            success=True,
            updated_at="2026-08-11T08:00:00Z",
            windows=[],
        )

    with patch(
        "app.quota_sync.fetch_quota_for_account",
        AsyncMock(side_effect=change_credential),
    ):
        await collect_due_quotas(owner_id="credential-change-test")

    assert db.get_quota_snapshot_attempt("opencode", account.id) is None
    assert db.get_cached_opencode_quota(account.id)["success"] is False


@pytest.mark.asyncio
async def test_quota_guard_rejects_change_at_database_write_boundary(temp_data_dir):
    account = db.create_opencode_account(
        name="Boundary", workspace_id="Default", auth_cookie="auth=old"
    )
    result = QuotaAccount(
        index=0,
        name="Boundary",
        workspace_id="wrk_old",
        success=True,
        updated_at="2026-08-14T00:00:00Z",
        windows=[],
    )
    original_record = db.record_opencode_quota_snapshot

    def change_then_record(*args, **kwargs):
        db.update_opencode_account(account.id, auth_cookie="auth=new")
        return original_record(*args, **kwargs)

    with (
        patch("app.quota_sync.fetch_quota_for_account", AsyncMock(return_value=result)),
        patch(
            "app.quota_sync.db.record_opencode_quota_snapshot",
            side_effect=change_then_record,
        ),
    ):
        assert await collect_opencode_account(account) is False

    assert db.get_quota_snapshot_attempt("opencode", account.id) is None


@pytest.mark.asyncio
async def test_quota_guard_rejects_lease_lost_at_database_write_boundary(temp_data_dir):
    account = db.create_opencode_account(
        name="Lease Boundary", workspace_id="Default", auth_cookie="auth=old"
    )
    assert db.acquire_scheduler_lease("quota-boundary", "owner-a") is True
    result = QuotaAccount(
        index=0,
        name="Lease Boundary",
        workspace_id="wrk_old",
        success=True,
        updated_at="2026-08-14T00:00:00Z",
        windows=[],
    )

    async def release_lease(*_args, **_kwargs):
        db.release_scheduler_lease("quota-boundary", "owner-a")
        return result

    with patch(
        "app.quota_sync.fetch_quota_for_account",
        AsyncMock(side_effect=release_lease),
    ):
        with pytest.raises(QuotaCollectionInterrupted):
            await collect_opencode_account(
                account,
                lease_check=lambda: True,
                lease_name="quota-boundary",
                lease_owner_id="owner-a",
            )

    assert db.get_quota_snapshot_attempt("opencode", account.id) is None


def test_quota_sync_settings_migrate_and_enforce_five_minute_minimum(temp_data_dir):
    migrated = merge_settings_with_defaults(
        {
            "refresh": {
                "ollama": {"auto_refresh": False, "interval_sec": "invalid"},
                "opencode_go": {"auto_refresh": True, "interval_sec": 30},
            }
        }
    )
    assert migrated["quota_sync"]["ollama"] == {
        "auto_sync": False,
        "interval_sec": 1800,
    }
    assert migrated["quota_sync"]["opencode_go"] == {
        "auto_sync": True,
        "interval_sec": 300,
    }

    save_settings_payload(
        {
            "quota_sync": {
                "ollama": {"interval_sec": 1},
                "opencode_go": {"interval_sec": "bad"},
            }
        }
    )
    service = load_service_config()
    assert service.quota_sync_ollama.interval_sec == 300
    assert service.quota_sync_opencode_go.interval_sec == 1800
