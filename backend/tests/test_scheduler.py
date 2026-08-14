from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app import db
from app.main import USAGE_SYNC_LEASE_NAME, _sync_due_usage_accounts
from app.main import usage_backfill, usage_sync
from app.quota import QuotaAccount
from app.quota_sync import QUOTA_LEASE_NAME, collect_due_quotas


def test_scheduler_lease_competition_renewal_takeover_and_release(temp_data_dir):
    now = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
    assert db.acquire_scheduler_lease("test", "owner-a", now=now) is True
    assert db.acquire_scheduler_lease("test", "owner-b", now=now) is False

    assert db.renew_scheduler_lease(
        "test", "owner-a", now=now + timedelta(seconds=30)
    ) is True
    assert db.acquire_scheduler_lease(
        "test", "owner-b", now=now + timedelta(seconds=121)
    ) is False
    assert db.acquire_scheduler_lease(
        "test", "owner-b", now=now + timedelta(seconds=151)
    ) is True
    assert db.release_scheduler_lease("test", "owner-a") is False
    assert db.release_scheduler_lease("test", "owner-b") is True


@pytest.mark.asyncio
async def test_quota_lease_prevents_second_owner_from_collecting(temp_data_dir):
    db.create_opencode_account(
        name="Due", workspace_id="Default", auth_cookie="auth=secret"
    )
    assert db.acquire_scheduler_lease(QUOTA_LEASE_NAME, "owner-a") is True
    fetch = AsyncMock()
    with patch("app.quota_sync.fetch_quota_for_account", fetch):
        await collect_due_quotas(owner_id="owner-b")
    fetch.assert_not_awaited()

    db.release_scheduler_lease(QUOTA_LEASE_NAME, "owner-a")
    fetch.return_value = QuotaAccount(
        index=0,
        name="Due",
        workspace_id="wrk_due",
        success=True,
        updated_at="2026-08-11T08:00:00Z",
        windows=[],
    )
    with patch("app.quota_sync.fetch_quota_for_account", fetch):
        await collect_due_quotas(owner_id="owner-b")
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_sync_lease_and_last_sync_deadline_prevent_duplicate_fetches(
    temp_data_dir,
):
    account = db.create_opencode_account(
        name="Usage", workspace_id="Default", auth_cookie="auth=secret"
    )
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    db.update_usage_sync_state(account.id, last_sync_at=now, last_sync_status="ok")

    sync = AsyncMock()
    with patch("app.main.sync_usage_incremental", sync):
        await _sync_due_usage_accounts(owner_id="owner-a")
    sync.assert_not_awaited()

    db.update_usage_sync_state(account.id, last_sync_at=None)
    assert db.acquire_scheduler_lease(USAGE_SYNC_LEASE_NAME, "owner-a") is True
    with patch("app.main.sync_usage_incremental", sync):
        await _sync_due_usage_accounts(owner_id="owner-b")
    sync.assert_not_awaited()

    db.release_scheduler_lease(USAGE_SYNC_LEASE_NAME, "owner-a")
    with patch("app.main.sync_usage_incremental", sync):
        await _sync_due_usage_accounts(owner_id="owner-b")
    sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_usage_actions_share_automatic_scheduler_lease(temp_data_dir):
    account = db.create_opencode_account(
        name="Usage", workspace_id="Default", auth_cookie="auth=secret"
    )
    assert db.acquire_scheduler_lease(USAGE_SYNC_LEASE_NAME, "automatic-owner") is True

    incremental = AsyncMock()
    backfill = AsyncMock()
    with (
        patch("app.main.sync_usage_incremental", incremental),
        patch("app.main.backfill_usage", backfill),
    ):
        with pytest.raises(Exception) as sync_error:
            await usage_sync(account.id)
        with pytest.raises(Exception) as backfill_error:
            await usage_backfill(account.id, pages=2)

    assert getattr(sync_error.value, "status_code", None) == 409
    assert getattr(backfill_error.value, "status_code", None) == 409
    incremental.assert_not_awaited()
    backfill.assert_not_awaited()
