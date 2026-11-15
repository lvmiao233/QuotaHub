from datetime import UTC, datetime

from app.mistral_quota import MONTHLY_POOL_USD, parse_mistral_public_budget_payload

USER_LIVE_BUDGET = {
    "vibe_budget": {
        "usage_percentage": 10.437228846666667,
        "initial_budget": 150.0,
        "currency": "USD",
        "reset_at": "2026-12-01T00:00:00Z",
        "payg_enabled": False,
    },
    "api_budget": {
        "usage_percentage": 0.0,
        "initial_budget": 15.0,
        "currency": "USD",
        "reset_at": "2026-12-01T00:00:00Z",
        "payg_enabled": False,
    },
}


def test_parse_mistral_public_budget_merged_against_150_pool():
    now = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)
    payload = {
        "vibe_budget": {
            "usage_percentage": 25.0,
            "initial_budget": 150,
            "currency": "USD",
            "reset_at": "2026-12-01T00:00:00.000Z",
        },
        "api_budget": {
            "usage_percentage": 10.0,
            "initial_budget": 100,
            "currency": "USD",
            "reset_at": "2026-12-01T00:00:00.000Z",
        },
    }
    windows = parse_mistral_public_budget_payload(payload, now)
    expected_used = 47.5 / MONTHLY_POOL_USD * 100.0
    assert abs(windows[0].used - expected_used) < 0.01
    assert not windows[0].status_text


def test_parse_mistral_public_budget_user_live_sample():
    now = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)
    windows = parse_mistral_public_budget_payload(USER_LIVE_BUDGET, now)
    assert abs(windows[0].used - 10.437228846666667) < 0.001
    assert not windows[0].status_text