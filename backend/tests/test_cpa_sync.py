from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app import db
from app.cpa_quota import (
    CPAAccountQuota,
    CPAAuthAccount,
    CPAChannelAuthenticationError,
    CPAError,
)
from app.quota_sync import (
    QuotaCollectionInterrupted,
    _is_fresh_cpa_observation,
    collect_cpa_channel,
)


def _account(index: int) -> CPAAuthAccount:
    return CPAAuthAccount(
        auth_index=f"raw-auth-{index}",
        auth_file_name=f"account-{index}.json",
        account_key_hash=f"hash-{index}",
        account_display=f"u{index}***@example.com",
        plan="Plus",
    )


@pytest.mark.asyncio
async def test_cpa_account_failure_isolated_and_channel_succeeds(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="secret",
    )
    discover = AsyncMock(return_value=[_account(1), _account(2)])
    fetch = AsyncMock(
        side_effect=[
            CPAError("单账号失败"),
            [
                {
                    "label": "5h Rolling",
                    "used": 10,
                    "remaining": 90,
                    "total": 100,
                    "unit": "%",
                    "reset_at": "",
                    "reset_in_sec": 0,
                }
            ],
        ]
    )
    with (
        patch("app.quota_sync.discover_cpa_accounts", discover),
        patch("app.quota_sync.fetch_cpa_header_snapshots", AsyncMock(return_value=[])),
        patch("app.quota_sync.fetch_cpa_account_quota", fetch),
        patch("app.quota_sync.REQUEST_PACING_SECONDS", 0),
    ):
        await collect_cpa_channel(channel)

    assert fetch.await_count == 2
    cached = db.list_cached_cpa_channels(enabled_only=False)[0]
    assert cached["success"] is True
    assert len(cached["accounts"]) == 2
    assert cached["accounts"][0]["success"] is False
    assert cached["accounts"][1]["success"] is True
    assert cached["accounts"][1]["quota_source"] == "active_api"


@pytest.mark.asyncio
async def test_cpa_channel_auth_failure_stops_remaining_accounts_and_marks_stale(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="secret",
    )
    db.record_cpa_quota_snapshot(
        channel.id,
        "hash-1",
        account_display="u1***@example.com",
        plan="Plus",
        success=True,
        windows=[],
    )
    db.record_cpa_channel_attempt(channel.id, success=True)
    discover = AsyncMock(return_value=[_account(1), _account(2)])
    fetch = AsyncMock(side_effect=CPAChannelAuthenticationError("bad management key"))

    with (
        patch("app.quota_sync.discover_cpa_accounts", discover),
        patch("app.quota_sync.fetch_cpa_header_snapshots", AsyncMock(return_value=[])),
        patch("app.quota_sync.fetch_cpa_account_quota", fetch),
        patch("app.quota_sync.REQUEST_PACING_SECONDS", 0),
    ):
        await collect_cpa_channel(db.get_cpa_channel(channel.id))

    fetch.assert_awaited_once()
    cached = db.list_cached_cpa_channels(enabled_only=False)[0]
    assert cached["success"] is False
    assert cached["stale"] is True
    assert cached["error"] == "CPA 管理认证失败，请检查管理密钥"
    assert cached["accounts"][0]["stale"] is True


@pytest.mark.asyncio
async def test_cpa_discovery_hides_removed_or_disabled_accounts_but_retains_snapshot(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="secret",
    )
    db.record_cpa_quota_snapshot(
        channel.id,
        "old-hash",
        account_display="o***@example.com",
        plan="Free",
        success=True,
        windows=[],
    )
    with (
        patch("app.quota_sync.discover_cpa_accounts", AsyncMock(return_value=[])),
        patch("app.quota_sync.fetch_cpa_header_snapshots", AsyncMock(return_value=[])),
    ):
        await collect_cpa_channel(channel)

    assert db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"] == []
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT visible, stale FROM cpa_quota_snapshots WHERE channel_id = ?",
            (channel.id,),
        ).fetchone()
    assert row["visible"] == 0
    assert row["stale"] == 1


@pytest.mark.asyncio
async def test_cpa_stops_remaining_accounts_and_discards_result_after_lease_loss(
    temp_data_dir,
):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="secret",
    )
    lease_valid = True
    discover = AsyncMock(return_value=[_account(1), _account(2)])

    async def lose_lease(*_args, **_kwargs):
        nonlocal lease_valid
        lease_valid = False
        return []

    fetch = AsyncMock(side_effect=lose_lease)
    with (
        patch("app.quota_sync.discover_cpa_accounts", discover),
        patch("app.quota_sync.fetch_cpa_header_snapshots", AsyncMock(return_value=[])),
        patch("app.quota_sync.fetch_cpa_account_quota", fetch),
        patch("app.quota_sync.REQUEST_PACING_SECONDS", 0),
    ):
        with pytest.raises(QuotaCollectionInterrupted):
            await collect_cpa_channel(
                channel, lease_check=lambda: lease_valid, run_id="lease-test"
            )

    fetch.assert_awaited_once()
    current = db.get_cpa_channel(channel.id)
    assert current is not None
    assert current.last_attempt_at is None
    assert db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"] == []


@pytest.mark.asyncio
async def test_cpa_active_fallback_is_throttled_when_lease_is_lost_after_request(
    temp_data_dir,
):
    channel = db.create_cpa_channel(
        name="CPA", base_url="https://proxy.example.com", management_key="secret"
    )
    account = _account(1)
    lease_valid = True

    async def lose_lease(*_args, **_kwargs):
        nonlocal lease_valid
        lease_valid = False
        return []

    active = AsyncMock(side_effect=lose_lease)
    with (
        patch("app.quota_sync.discover_cpa_accounts", AsyncMock(return_value=[account])),
        patch("app.quota_sync.fetch_cpa_header_snapshots", AsyncMock(return_value=[])),
        patch("app.quota_sync.fetch_cpa_account_quota", active),
    ):
        with pytest.raises(QuotaCollectionInterrupted):
            await collect_cpa_channel(channel, lease_check=lambda: lease_valid)

        lease_valid = True
        assert await collect_cpa_channel(
            db.get_cpa_channel(channel.id), lease_check=lambda: lease_valid
        ) is True

    active.assert_awaited_once()


@pytest.mark.asyncio
async def test_cpa_passive_snapshot_success_avoids_active_api_call(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA", base_url="https://proxy.example.com", management_key="secret"
    )
    account = _account(1)
    passive = AsyncMock(
        return_value=[
            {
                "timestamp_ms": int(datetime.now(UTC).timestamp() * 1000),
                "auth_file_snapshot": account.auth_file_name,
                "auth_index": account.auth_index,
                "response_metadata": {
                    "quota": {
                        "plan_type": "free",
                        "primary": {
                            "used_percent": 15,
                            "window_minutes": 300,
                        },
                    }
                },
            }
        ]
    )
    active = AsyncMock()
    with (
        patch("app.quota_sync.discover_cpa_accounts", AsyncMock(return_value=[account])),
        patch("app.quota_sync.fetch_cpa_header_snapshots", passive),
        patch("app.quota_sync.fetch_cpa_account_quota", active),
    ):
        assert await collect_cpa_channel(channel) is True

    active.assert_not_awaited()
    cached = db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"][0]
    assert cached["plan"] == "Free"
    assert cached["quota_source"] == "response_header"


@pytest.mark.asyncio
async def test_cpa_active_fallback_attempt_is_throttled_for_twelve_hours_even_after_failure(
    temp_data_dir,
):
    channel = db.create_cpa_channel(
        name="CPA", base_url="https://proxy.example.com", management_key="secret"
    )
    account = _account(1)
    discover = AsyncMock(return_value=[account])
    passive = AsyncMock(return_value=[])
    active = AsyncMock(side_effect=CPAError("active failed"))
    with (
        patch("app.quota_sync.discover_cpa_accounts", discover),
        patch("app.quota_sync.fetch_cpa_header_snapshots", passive),
        patch("app.quota_sync.fetch_cpa_account_quota", active),
    ):
        assert await collect_cpa_channel(channel) is True
        assert await collect_cpa_channel(db.get_cpa_channel(channel.id)) is True

    active.assert_awaited_once()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT last_active_attempt_at FROM cpa_quota_snapshots WHERE channel_id = ?",
            (channel.id,),
        ).fetchone()
    assert row["last_active_attempt_at"] is not None


@pytest.mark.asyncio
async def test_cpa_stale_passive_snapshot_uses_due_active_fallback(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA", base_url="https://proxy.example.com", management_key="secret"
    )
    account = _account(1)
    stale_at = datetime.now(UTC) - timedelta(days=31)
    active = AsyncMock(return_value=[])
    with (
        patch("app.quota_sync.discover_cpa_accounts", AsyncMock(return_value=[account])),
        patch(
            "app.quota_sync.fetch_cpa_header_snapshots",
            AsyncMock(
                return_value=[
                    {
                        "timestamp_ms": int(stale_at.timestamp() * 1000),
                        "auth_file_snapshot": account.auth_file_name,
                        "auth_index": account.auth_index,
                        "response_metadata": {
                            "quota": {"primary": {"used_percent": 10}}
                        },
                    }
                ]
            ),
        ),
        patch("app.quota_sync.fetch_cpa_account_quota", active),
    ):
        assert await collect_cpa_channel(channel) is True

    active.assert_awaited_once()


def test_cpa_passive_freshness_has_short_ttl_and_future_tolerance():
    now = datetime.now(UTC)
    assert _is_fresh_cpa_observation(
        (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    )
    assert not _is_fresh_cpa_observation(
        (now - timedelta(hours=7)).isoformat().replace("+00:00", "Z")
    )
    assert _is_fresh_cpa_observation(
        (now + timedelta(minutes=4)).isoformat().replace("+00:00", "Z")
    )
    assert not _is_fresh_cpa_observation(
        (now + timedelta(minutes=6)).isoformat().replace("+00:00", "Z")
    )


@pytest.mark.asyncio
async def test_cpa_active_response_plan_takes_precedence_over_auth_metadata(
    temp_data_dir,
):
    channel = db.create_cpa_channel(
        name="CPA", base_url="https://proxy.example.com", management_key="secret"
    )
    account = _account(1)
    active = AsyncMock(return_value=CPAAccountQuota(plan="Pro 20x", windows=[]))
    with (
        patch("app.quota_sync.discover_cpa_accounts", AsyncMock(return_value=[account])),
        patch("app.quota_sync.fetch_cpa_header_snapshots", AsyncMock(return_value=[])),
        patch("app.quota_sync.fetch_cpa_account_quota", active),
    ):
        assert await collect_cpa_channel(channel) is True

    active.assert_awaited_once()
    cached = db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"][0]
    assert cached["plan"] == "Pro 20x"


@pytest.mark.asyncio
async def test_cpa_unexpected_error_is_sanitized_in_sqlite(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA", base_url="https://proxy.example.com", management_key="secret"
    )
    sentinel = "cpa-error-secret-sentinel"
    with (
        patch(
            "app.quota_sync.discover_cpa_accounts",
            AsyncMock(return_value=[_account(1)]),
        ),
        patch("app.quota_sync.fetch_cpa_header_snapshots", AsyncMock(return_value=[])),
        patch(
            "app.quota_sync.fetch_cpa_account_quota",
            AsyncMock(side_effect=CPAError(sentinel)),
        ),
    ):
        assert await collect_cpa_channel(channel) is True

    cached = db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"][0]
    assert cached["error"] == "CPA 额度采集失败"
    assert sentinel.encode("utf-8") not in db.db_path().read_bytes()
