from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from .quota import (
    TIMEOUT,
    build_cookie_header,
    console_api_headers,
    require_console_session,
    resolve_workspace_id,
)

REQUEST_LOGS_URL = "https://opencode.ai/console/api/request-logs"
USAGE_PAGE_SIZE = 50
MAX_RESPONSE_BYTES = 4 << 20


@dataclass
class ParsedUsageRecord:
    usg_id: str
    created_at: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_raw: int
    cost_usd: float
    key_id: str
    plan: str | None = None

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "usg_id": self.usg_id,
            "created_at": self.created_at,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_raw": self.cost_raw,
            "cost_usd": self.cost_usd,
            "key_id": self.key_id,
            "plan": self.plan,
        }


@dataclass
class RequestLogsPage:
    records: list[ParsedUsageRecord]
    next_cursor: str | None


def _ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC).isoformat().replace("+00:00", "Z")


def _iso_to_ms(iso: str) -> int:
    text = iso.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return int(dt.timestamp() * 1000)


def iso_to_since_ms(iso: str | None) -> int | None:
    if not iso:
        return None
    return _iso_to_ms(iso)


def parse_request_log_item(item: dict[str, Any]) -> ParsedUsageRecord | None:
    record_id = str(item.get("id") or item.get("requestID") or "").strip()
    if not record_id:
        return None
    started = item.get("startedAt")
    if started is None:
        return None
    created_at = _ms_to_iso(int(started))
    cost_usd = float(item.get("cost") or 0.0)
    cost_raw = int(round(cost_usd * 1_000_000_000))
    product = item.get("product")
    plan = str(product) if product else None
    return ParsedUsageRecord(
        usg_id=record_id,
        created_at=created_at,
        model=str(item.get("model") or item.get("requestedModel") or ""),
        provider=str(item.get("provider") or ""),
        input_tokens=int(item.get("inputTokens") or 0),
        output_tokens=int(item.get("outputTokens") or 0),
        cost_raw=cost_raw,
        cost_usd=cost_usd,
        key_id=str(item.get("serviceAPIKeyID") or item.get("keyID") or ""),
        plan=plan,
    )


def parse_request_logs_payload(payload: dict[str, Any]) -> RequestLogsPage:
    records: list[ParsedUsageRecord] = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        parsed = parse_request_log_item(item)
        if parsed:
            records.append(parsed)
    next_cursor = payload.get("nextCursor")
    if next_cursor is not None and not str(next_cursor).strip():
        next_cursor = None
    return RequestLogsPage(records=records, next_cursor=next_cursor)


async def fetch_request_logs_page(
    *,
    workspace_id: str,
    auth_cookie: str,
    since_ms: int | None = None,
    cursor: str | None = None,
    limit: int = USAGE_PAGE_SIZE,
) -> RequestLogsPage:
    cookie_header = build_cookie_header(auth_cookie)
    if not cookie_header:
        raise ValueError("Console Cookie 为空")
    require_console_session(cookie_header)

    params: dict[str, str] = {
        "category": "inference",
        "limit": str(limit),
    }
    if since_ms is not None:
        params["since"] = str(since_ms)
    if cursor:
        params["cursor"] = cursor

    url = f"{REQUEST_LOGS_URL}?{urlencode(params)}"
    headers = console_api_headers(cookie_header, workspace_id)

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code in (401, 403):
            raise ValueError(f"认证失败 (HTTP {resp.status_code})，请检查 Console Cookie")
        if resp.status_code < 200 or resp.status_code >= 300:
            raise ValueError(f"request-logs 返回 HTTP {resp.status_code}")
        payload = resp.json()
        if not isinstance(payload, dict):
            raise ValueError("request-logs 响应格式无效")
        return parse_request_logs_payload(payload)


def resolve_account_workspace_id(
    workspace_hint: str, auth_cookie: str, resolved: str | None = None
) -> str:
    del auth_cookie
    return resolve_workspace_id(workspace_hint, resolved)
