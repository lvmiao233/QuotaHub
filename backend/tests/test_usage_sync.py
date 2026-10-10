from unittest.mock import AsyncMock, patch

import pytest

from app import db
from app.opencode_usage import ParsedUsageRecord, RequestLogsPage
from app.usage_sync import sync_usage_incremental


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
        workspace_id="wrk_test",
        auth_cookie="__Host-console_session=st_test",
    )


@pytest.mark.asyncio
async def test_incremental_stops_on_duplicate_page(account, monkeypatch):
    pages = [
        RequestLogsPage(records=[_record("log-1"), _record("log-2")], next_cursor=None),
    ]
    fetch_mock = AsyncMock(side_effect=pages)

    monkeypatch.setattr("app.usage_sync.fetch_request_logs_page", fetch_mock)
    result = await sync_usage_incremental(account)
    assert result.inserted == 2
    assert result.pages_fetched == 1

    fetch_mock.reset_mock()
    fetch_mock.side_effect = [
        RequestLogsPage(records=[_record("log-1"), _record("log-2")], next_cursor=None),
    ]
    result2 = await sync_usage_incremental(account)
    assert result2.inserted == 0
    assert result2.pages_fetched == 1
