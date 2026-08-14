from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import httpx
import pytest

from app import db
from app.cpa_quota import (
    CPAAccountQuota,
    CPAAuthAccount,
    CPAPassiveSnapshotsUnsupported,
    USER_AGENT,
    discover_cpa_accounts,
    fetch_cpa_header_snapshots,
    fetch_cpa_account_quota,
    match_cpa_header_snapshot,
    map_cpa_plan,
    mask_cpa_account,
    normalize_cpa_url,
    parse_cpa_account_quota,
    parse_auth_files,
    parse_cpa_header_snapshot,
    parse_cpa_usage_payload,
)
from app.quota import LABEL_ROLLING, LABEL_WEEKLY


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("free", "Free"),
        ("plus", "Plus"),
        ("prolite", "Pro 5x"),
        ("pro-lite", "Pro 5x"),
        ("pro_5x", "Pro 5x"),
        ("pro", "Pro 20x"),
        ("pro-20x", "Pro 20x"),
        ("team", "未知套餐"),
    ],
)
def test_cpa_plan_mapping(raw: str, expected: str):
    assert map_cpa_plan(raw) == expected


def test_cpa_url_and_account_masking():
    assert normalize_cpa_url(" HTTPS://proxy.example.com/root/ ") == "https://proxy.example.com/root"
    assert mask_cpa_account("alice@example.com") == "a***@example.com"
    assert mask_cpa_account("acct_123456789") == "ac***89"
    with pytest.raises(ValueError):
        normalize_cpa_url("proxy.example.com")
    with pytest.raises(ValueError):
        normalize_cpa_url("https://user:pass@proxy.example.com")


def test_parse_auth_files_filters_non_codex_and_disabled_without_leaking_identifiers(
    temp_data_dir,
):
    raw_email = "alice@example.com"
    raw_auth_index = "codex-auth-index-sensitive"
    accounts = parse_auth_files(
        {
            "files": [
                {
                            "provider": "codex",
                            "auth_index": raw_auth_index,
                            "name": "codex-account.json",
                    "email": raw_email,
                    "account_type": "prolite",
                    "disabled": False,
                    "unavailable": False,
                },
                {"provider": "codex", "auth_index": "disabled", "disabled": True},
                {"provider": "claude", "auth_index": "other"},
            ]
        }
    )
    assert len(accounts) == 1
    account = accounts[0]
    assert account.account_display == "a***@example.com"
    assert account.plan == "Pro 5x"
    assert account.auth_index == raw_auth_index
    assert account.auth_file_name == "codex-account.json"
    assert account.account_key_hash.startswith("hmac:v1:")
    assert account.legacy_account_key_hash == hashlib.sha256(
        raw_auth_index.encode("utf-8")
    ).hexdigest()
    assert raw_auth_index not in account.account_key_hash
    assert raw_email not in account.account_display


@pytest.mark.parametrize(
    ("plan_type", "expected"),
    [
        ("free", "Free"),
        ("plus", "Plus"),
        ("prolite", "Pro 5x"),
        ("pro", "Pro 20x"),
    ],
)
def test_parse_auth_files_prefers_cli_proxy_id_token_plan_over_oauth_kind(
    temp_data_dir, plan_type: str, expected: str
):
    account = parse_auth_files(
        {
            "files": [
                {
                    "provider": "codex",
                    "auth_index": f"auth-{plan_type}",
                    "account_type": "oauth",
                    "id_token": {
                        "chatgpt_account_id": "acct-sanitized",
                        "plan_type": plan_type,
                    },
                }
            ]
        }
    )[0]
    assert account.plan == expected


def test_auth_file_plan_priority_is_independent_of_json_field_order(temp_data_dir):
    account = parse_auth_files(
        {
            "files": [
                {
                    "provider": "codex",
                    "auth_index": "ordered-plan",
                    "id_token": {
                        "account_type": "oauth",
                        "chatgpt_plan_type": "plus",
                        "plan_type": "pro",
                        "chatgpt_account_id": "acct-plan-order",
                    },
                }
            ]
        }
    )[0]
    assert account.plan == "Pro 20x"


def test_legacy_cpa_sha_fingerprint_migrates_without_losing_snapshot(temp_data_dir):
    auth_index = "legacy-auth-index"
    old_hash = hashlib.sha256(auth_index.encode("utf-8")).hexdigest()
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="management-secret",
    )
    db.record_cpa_quota_snapshot(
        channel.id,
        old_hash,
        account_display="l***@example.com",
        plan="Plus",
        success=True,
        windows=[{"label": "5h Rolling", "remaining": 75}],
    )
    before = db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"][0]
    account = parse_auth_files(
        {
            "files": [
                {
                    "provider": "codex",
                    "auth_index": auth_index,
                    "email": "legacy@example.com",
                    "account_type": "plus",
                }
            ]
        }
    )[0]

    db.prepare_cpa_channel_discovery(
        channel.id,
        [
            (
                account.account_key_hash,
                account.legacy_account_key_hash,
                account.account_display,
                account.plan,
            )
        ],
    )

    after = db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"][0]
    assert after["public_id"] == before["public_id"]
    assert after["windows"] == before["windows"]
    with db.get_conn() as conn:
        stored_hash = conn.execute(
            "SELECT account_key_hash FROM cpa_quota_snapshots WHERE channel_id = ?",
            (channel.id,),
        ).fetchone()[0]
    assert stored_hash == account.account_key_hash
    assert stored_hash.startswith("hmac:v1:")


def test_same_auth_index_with_changed_account_subject_gets_new_public_identity(
    temp_data_dir,
):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="management-secret",
    )

    def parse(subject: str) -> CPAAuthAccount:
        return parse_auth_files(
            {
                "files": [
                    {
                        "provider": "codex",
                        "auth_index": "same-path-auth-index",
                        "name": "same-file.json",
                        "email": "same@example.com",
                        "id_token": {
                            "chatgpt_account_id": subject,
                            "plan_type": "plus",
                        },
                    }
                ]
            }
        )[0]

    first = parse("subject-a")
    db.prepare_cpa_channel_discovery(
        channel.id,
        [
            (
                first.account_key_hash,
                (first.previous_account_key_hash, first.legacy_account_key_hash),
                first.account_display,
                first.plan,
            )
        ],
    )
    first_public_id = db.record_cpa_quota_snapshot(
        channel.id,
        first.account_key_hash,
        account_display=first.account_display,
        plan=first.plan,
        success=True,
        windows=[{"label": "5h Rolling", "remaining": 50}],
    )
    db.record_cpa_active_attempt(
        channel.id,
        first.account_key_hash,
        account_display=first.account_display,
        plan=first.plan,
    )

    replacement = parse("subject-b")
    assert replacement.account_key_hash != first.account_key_hash
    db.prepare_cpa_channel_discovery(
        channel.id,
        [
            (
                replacement.account_key_hash,
                (
                    replacement.previous_account_key_hash,
                    replacement.legacy_account_key_hash,
                ),
                replacement.account_display,
                replacement.plan,
            )
        ],
    )
    assert db.get_cpa_active_attempt(channel.id, replacement.account_key_hash) is None
    replacement_public_id = db.record_cpa_quota_snapshot(
        channel.id,
        replacement.account_key_hash,
        account_display=replacement.account_display,
        plan=replacement.plan,
        success=True,
        windows=[],
    )

    assert replacement_public_id != first_public_id
    cached = db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"]
    assert [item["public_id"] for item in cached] == [replacement_public_id]
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT account_key_hash, visible
            FROM cpa_quota_snapshots WHERE channel_id = ?
            ORDER BY created_at
            """,
            (channel.id,),
        ).fetchall()
    assert {row["account_key_hash"] for row in rows} == {
        first.account_key_hash,
        replacement.account_key_hash,
    }
    assert sorted(int(row["visible"]) for row in rows) == [0, 1]
    raw_db = db.db_path().read_bytes()
    assert b"subject-a" not in raw_db
    assert b"subject-b" not in raw_db


def test_parse_usage_items_response_metadata_quota_windows():
    now = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
    windows = parse_cpa_usage_payload(
        {
            "items": [
                {
                    "response_metadata": {
                        "quota": {
                            "primary": {
                                "used_percent": 12.5,
                                "reset_after_seconds": 1800,
                                "limit_window_seconds": 18000,
                            },
                            "secondary": {
                                "used_percent": 40,
                                "reset_at": "2026-08-16T08:00:00Z",
                                "limit_window_seconds": 604800,
                            },
                        }
                    }
                }
            ]
        },
        now=now,
    )
    assert [window["label"] for window in windows] == [LABEL_ROLLING, LABEL_WEEKLY]
    assert windows[0]["remaining"] == 87.5
    assert windows[0]["reset_in_sec"] == 1800
    assert windows[1]["remaining"] == 60.0


def test_active_usage_result_preserves_plan_type():
    result = parse_cpa_account_quota(
        {
            "plan_type": "pro",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 25,
                    "limit_window_seconds": 18000,
                }
            },
        }
    )
    assert isinstance(result, CPAAccountQuota)
    assert result.plan == "Pro 20x"
    assert result.windows[0]["remaining"] == 75.0


def test_header_snapshot_matches_latest_file_and_auth_index_without_cross_account_leak(
    temp_data_dir,
):
    accounts = parse_auth_files(
        {
            "files": [
                {
                    "provider": "codex",
                    "name": "shared.json",
                    "auth_index": "idx-a",
                    "email": "alpha@example.com",
                },
                {
                    "provider": "codex",
                    "name": "shared.json",
                    "auth_index": "idx-b",
                    "email": "beta@example.com",
                },
            ]
        }
    )
    items = [
        {
            "timestamp_ms": 1_700_000_000_000,
            "auth_file_snapshot": "shared.json",
            "auth_index": "idx-b",
            "response_metadata": {"quota": {"plan_type": "plus", "primary": {"used_percent": 70}}},
        },
        {
            "timestamp_ms": 1_700_000_010_000,
            "auth_file_snapshot": "shared.json",
            "auth_index": "idx-a",
            "response_metadata": {"quota": {"plan_type": "free", "primary": {"used_percent": 10}}},
        },
        {
            "timestamp_ms": 1_700_000_020_000,
            "auth_file_snapshot": "shared.json",
            "auth_index": "idx-a",
            "response_metadata": {"quota": {"plan_type": "pro", "primary": {"used_percent": 20}}},
        },
    ]

    matched_a = match_cpa_header_snapshot(accounts[0], items)
    matched_b = match_cpa_header_snapshot(accounts[1], items)

    assert matched_a is items[2]
    assert matched_b is items[0]


def test_header_snapshot_parser_anchors_relative_reset_to_observation_time():
    observed_at = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
    parsed = parse_cpa_header_snapshot(
        {
            "timestamp_ms": int(observed_at.timestamp() * 1000),
            "response_metadata": {
                "quota": {
                    "plan_type": "prolite",
                    "primary": {
                        "used_percent": 25,
                        "reset_after_seconds": 1800,
                        "window_minutes": 300,
                    },
                    "secondary": {
                        "used_percent": 40,
                        "reset_at_ms": int((observed_at.timestamp() + 604800) * 1000),
                        "window_minutes": 10080,
                    },
                }
            },
        },
        now=observed_at,
    )

    assert parsed.plan == "Pro 5x"
    assert parsed.observed_at == "2026-08-11T08:00:00Z"
    assert parsed.windows[0]["duration_sec"] == 18000
    assert parsed.windows[0]["reset_at"] == "2026-08-11T08:30:00Z"
    assert parsed.windows[1]["duration_sec"] == 604800


@pytest.mark.asyncio
async def test_header_snapshot_endpoint_404_is_capability_downgrade(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="management-secret",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v0/management/monitoring/header-snapshots"
        assert dict(request.url.params) == {"days": "30", "limit": "1000"}
        return httpx.Response(404, json={"error": "not found"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CPAPassiveSnapshotsUnsupported):
            await fetch_cpa_header_snapshots(channel, client)


@pytest.mark.asyncio
async def test_cpa_protocol_uses_fixed_management_endpoints_and_usage_request(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="management-secret",
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == "Bearer management-secret"
        if request.method == "GET":
            assert request.url.path == "/v0/management/auth-files"
            return httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "provider": "codex",
                            "auth_index": "auth-1",
                            "name": "codex-auth.json",
                            "email": "person@example.com",
                            "account_type": "plus",
                        }
                    ]
                },
            )
        assert request.method == "POST"
        assert request.url.path == "/v0/management/api-call"
        body = json.loads(request.content)
        assert body == {
            "auth_index": "auth-1",
            "method": "GET",
            "url": "https://chatgpt.com/backend-api/wham/usage",
            "header": {
                "Authorization": "Bearer $TOKEN$",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        }
        return httpx.Response(
            200,
            json={
                "status_code": 200,
                "body": json.dumps(
                    {
                        "rate_limit": {
                            "primary_window": {
                                "used_percent": 25,
                                "reset_after_seconds": 900,
                                "limit_window_seconds": 18000,
                            }
                        }
                    }
                ),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        accounts = await discover_cpa_accounts(channel, client)
        windows = await fetch_cpa_account_quota(channel, accounts[0], client)

    assert len(seen) == 2
    assert accounts[0].account_display == "p***@example.com"
    assert windows[0]["label"] == LABEL_ROLLING
    assert windows[0]["remaining"] == 75.0
