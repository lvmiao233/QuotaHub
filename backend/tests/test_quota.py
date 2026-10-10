from datetime import UTC, datetime

from app.opencode_usage import parse_request_log_item, parse_request_logs_payload
from app.quota import build_cookie_header, parse_go_status_payload


def test_build_cookie_header_session():
    assert build_cookie_header("st_abc") == "__Host-console_session=st_abc"


def test_build_cookie_header_preserves_parts():
    cookie = "__Host-console_session=st_x; auth=Fe26.2**token"
    assert "auth=" in build_cookie_header(cookie)
    assert "__Host-console_session=" in build_cookie_header(cookie)


def test_parse_go_status_payload():
    payload = {
        "access": {
            "meters": {
                "fiveHour": {
                    "limitMicroCents": "1200000000",
                    "usedMicroCents": "0",
                    "resetsAt": None,
                },
                "week": {
                    "limitMicroCents": "3000000000",
                    "usedMicroCents": "1500000000",
                    "resetsAt": "2026-10-12T00:00:00.000Z",
                },
                "month": {
                    "limitMicroCents": "6000000000",
                    "usedMicroCents": "3000000000",
                    "resetsAt": "2026-10-27T12:20:30.000Z",
                },
            }
        }
    }
    now = datetime(2026, 10, 10, 4, 0, 0, tzinfo=UTC)
    windows = parse_go_status_payload(payload, now)
    assert len(windows) == 3
    assert windows[0].label == "5h Rolling"
    assert windows[0].used == 0.0
    assert windows[1].used == 50.0
    assert windows[2].used == 50.0
    assert windows[1].reset_in_sec > 0


def test_parse_request_logs_payload():
    payload = {
        "items": [
            {
                "id": "b6ddb01a-3204-455f-85a8-654e227a0f57",
                "startedAt": 1791604010180,
                "model": "deepseek-v4-flash",
                "provider": "opencode",
                "inputTokens": 84,
                "outputTokens": 21,
                "cost": 0.0000252,
                "serviceAPIKeyID": "key_01",
                "product": "go",
            }
        ],
        "nextCursor": '{"v":2}',
    }
    page = parse_request_logs_payload(payload)
    assert len(page.records) == 1
    assert page.records[0].usg_id.startswith("b6ddb01a")
    assert page.records[0].cost_usd == 0.0000252
    assert page.next_cursor == '{"v":2}'


def test_parse_request_log_item():
    item = parse_request_log_item({"id": "x", "startedAt": 1791604010180, "cost": 1.0})
    assert item is not None
    assert item.cost_raw == 1_000_000_000
