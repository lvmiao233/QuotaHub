from unittest.mock import AsyncMock, patch

import pytest

from app import db
from app.usage_sync import UsageSyncInterrupted, sync_usage_incremental
from app.opencode_usage import ParsedUsageRecord


def _record(usg_id: str) -> ParsedUsageRecord:
    return ParsedUsageRecord(
        usg_id=usg_id,
        created_at="2026-07-09T08:16:06.000Z",
        model="glm-5.2",
        provider="p",
        input_tokens=1,
        output_tokens=1,
        cost_raw=1000,
        cost_usd=1e-6,
        key_id="key_x",
    )


@pytest.fixture()
def account(temp_data_dir):
    return db.create_opencode_account(
        name="sync-test",
        workspace_id="Default",
        auth_cookie="auth=t",
    )


@pytest.mark.asyncio
async def test_incremental_stops_on_duplicate_page(account, monkeypatch):
    page_data = {
        0: [_record("usg_new1"), _record("usg_new2")],
        1: [],
    }

    async def fake_fetch(**kwargs):
        page = kwargs.get("page", 0)
        return page_data.get(page, [])

    monkeypatch.setattr(
        "app.usage_sync.fetch_usage_page",
        AsyncMock(side_effect=fake_fetch),
    )
    monkeypatch.setattr(
        "app.usage_sync.resolve_account_workspace_id",
        AsyncMock(return_value="wrk_test"),
    )

    result = await sync_usage_incremental(account)
    assert result.inserted == 2
    assert result.pages_fetched == 1

    page_data[0] = [_record("usg_new1"), _record("usg_new2")]
    result2 = await sync_usage_incremental(account)
    assert result2.inserted == 0
    assert result2.pages_fetched == 1


@pytest.mark.asyncio
async def test_incremental_discards_page_after_credential_change(account, monkeypatch):
    async def fake_fetch(**_kwargs):
        db.update_opencode_account(account.id, auth_cookie="auth=changed")
        return [_record("usg_stale")]

    monkeypatch.setattr(
        "app.usage_sync.fetch_usage_page", AsyncMock(side_effect=fake_fetch)
    )
    monkeypatch.setattr(
        "app.usage_sync.resolve_account_workspace_id",
        AsyncMock(return_value="wrk_test"),
    )

    result = await sync_usage_incremental(account)
    assert result.error == "账号配置已变化，已丢弃本次同步结果"
    assert db.list_usage_records(account.id)[1] == 0
    assert db.get_usage_sync_state(account.id).last_sync_at is None


@pytest.mark.asyncio
async def test_incremental_stops_before_writing_or_fetching_again_after_lease_loss(
    account, monkeypatch
):
    lease_valid = True

    async def fake_fetch(**_kwargs):
        nonlocal lease_valid
        lease_valid = False
        return [_record("usg_lease_lost")]

    fetch = AsyncMock(side_effect=fake_fetch)
    monkeypatch.setattr("app.usage_sync.fetch_usage_page", fetch)
    monkeypatch.setattr(
        "app.usage_sync.resolve_account_workspace_id",
        AsyncMock(return_value="wrk_test"),
    )

    with pytest.raises(UsageSyncInterrupted):
        await sync_usage_incremental(
            account, continuation_check=lambda: lease_valid
        )

    fetch.assert_awaited_once()
    assert db.list_usage_records(account.id)[1] == 0
    assert db.get_usage_sync_state(account.id).last_sync_at is None


@pytest.mark.asyncio
async def test_unexpected_sync_error_is_sanitized_in_sqlite(account, monkeypatch):
    sentinel = "unexpected-sync-secret-sentinel"
    monkeypatch.setattr(
        "app.usage_sync.resolve_account_workspace_id",
        AsyncMock(return_value="wrk_test"),
    )
    monkeypatch.setattr(
        "app.usage_sync.fetch_usage_page",
        AsyncMock(side_effect=RuntimeError(sentinel)),
    )

    with pytest.raises(RuntimeError, match=sentinel):
        await sync_usage_incremental(account)

    state = db.get_usage_sync_state(account.id)
    assert state.last_sync_error == "使用记录同步失败"
    assert sentinel.encode("utf-8") not in db.db_path().read_bytes()


@pytest.mark.asyncio
async def test_incremental_guard_rejects_change_at_database_write_boundary(
    account, monkeypatch
):
    monkeypatch.setattr(
        "app.usage_sync.resolve_account_workspace_id",
        AsyncMock(return_value="wrk_test"),
    )
    monkeypatch.setattr(
        "app.usage_sync.fetch_usage_page",
        AsyncMock(return_value=[_record("usg-boundary")]),
    )
    original_insert = db.insert_usage_records_ignore

    def change_then_insert(*args, **kwargs):
        db.update_opencode_account(account.id, auth_cookie="auth=changed-at-write")
        return original_insert(*args, **kwargs)

    monkeypatch.setattr(
        "app.usage_sync.db.insert_usage_records_ignore", change_then_insert
    )

    result = await sync_usage_incremental(account)

    assert result.error == "账号配置已变化，已丢弃本次同步结果"
    assert db.list_usage_records(account.id)[1] == 0
    assert db.get_usage_sync_state(account.id).last_sync_at is None
