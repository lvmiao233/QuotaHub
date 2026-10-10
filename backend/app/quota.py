from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import AccountConfig

CONSOLE_GO_STATUS_URL = "https://opencode.ai/console/api/go/status"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/148.0"
TIMEOUT = 15.0

LABEL_ROLLING = "5h Rolling"
LABEL_WEEKLY = "Weekly"
LABEL_MONTHLY = "Monthly"

METER_KEYS = (
    (LABEL_ROLLING, "fiveHour"),
    (LABEL_WEEKLY, "week"),
    (LABEL_MONTHLY, "month"),
)

RE_WORKSPACE_ID = re.compile(r"wrk_[A-Za-z0-9]+")


@dataclass
class QuotaWindow:
    label: str
    used: float
    remaining: float
    total: float
    unit: str
    reset_at: str
    reset_in_sec: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "used": self.used,
            "remaining": self.remaining,
            "total": self.total,
            "unit": self.unit,
            "reset_at": self.reset_at,
            "reset_in_sec": self.reset_in_sec,
        }


@dataclass
class QuotaAccount:
    index: int
    name: str
    workspace_id: str
    success: bool
    updated_at: str
    windows: list[QuotaWindow]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "index": self.index,
            "name": self.name,
            "workspace_id": self.workspace_id,
            "success": self.success,
            "updated_at": self.updated_at,
        }
        if self.error:
            payload["error"] = self.error
        if self.windows:
            payload["windows"] = [w.to_dict() for w in self.windows]
        return payload


def build_cookie_header(auth_cookie: str) -> str:
    cookie = auth_cookie.strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie[7:].strip()
    if not cookie:
        return ""

    parts: list[str] = []
    seen: set[str] = set()
    for segment in cookie.split(";"):
        segment = segment.strip()
        if not segment or "=" not in segment:
            continue
        name = segment.split("=", 1)[0].strip().lower()
        if name in seen:
            continue
        seen.add(name)
        parts.append(segment)
    if parts:
        return "; ".join(parts)

    if cookie.startswith("st_"):
        return f"__Host-console_session={cookie}"
    if cookie.startswith("Fe26."):
        return f"auth={cookie}"
    return f"__Host-console_session={cookie}"


def require_console_session(cookie_header: str) -> None:
    if "__Host-console_session=" not in cookie_header:
        raise ValueError("缺少 __Host-console_session，请从 OpenCode Console 复制 Cookie")


def extract_workspace_id(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith("wrk_") and len(value) > 4:
        return value
    match = RE_WORKSPACE_ID.search(value)
    return match.group(0) if match else ""


def resolve_workspace_id(workspace_hint: str, resolved: str | None = None) -> str:
    if resolved and resolved.startswith("wrk_"):
        return resolved
    org_id = extract_workspace_id(workspace_hint)
    if org_id:
        return org_id
    hint = workspace_hint.strip()
    if hint and hint.lower() != "default":
        raise ValueError(f'无法从 "{hint}" 解析工作区 ID，请填写 wrk_ 开头的组织 ID')
    raise ValueError("workspace_id 必须是 wrk_...（Console 地址栏或设置中的组织 ID）")


def console_api_headers(cookie_header: str, org_id: str) -> dict[str, str]:
    return {
        "Cookie": cookie_header,
        "x-org-id": org_id,
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Referer": f"https://opencode.ai/console/{org_id}/go",
    }


def _parse_reset_at(value: str | None, now: datetime) -> tuple[str, int]:
    if not value:
        return "", 0
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        reset_dt = datetime.fromisoformat(text)
    except ValueError:
        return "", 0
    if reset_dt.tzinfo is None:
        reset_dt = reset_dt.replace(tzinfo=UTC)
    else:
        reset_dt = reset_dt.astimezone(UTC)
    reset_in_sec = max(0, int((reset_dt - now).total_seconds()))
    return reset_dt.isoformat().replace("+00:00", "Z"), reset_in_sec


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))


def parse_go_status_payload(payload: dict[str, Any], now: datetime) -> list[QuotaWindow]:
    meters = (payload.get("access") or {}).get("meters") or {}
    windows: list[QuotaWindow] = []
    for label, key in METER_KEYS:
        meter = meters.get(key) or {}
        limit_raw = meter.get("limitMicroCents")
        used_raw = meter.get("usedMicroCents")
        if limit_raw is None or used_raw is None:
            continue
        limit = int(limit_raw)
        used_micro = int(used_raw)
        if limit <= 0:
            continue
        used_pct = _clamp_percent(used_micro / limit * 100.0)
        reset_at, reset_in_sec = _parse_reset_at(meter.get("resetsAt"), now)
        windows.append(
            QuotaWindow(
                label=label,
                used=used_pct,
                remaining=100.0 - used_pct,
                total=100.0,
                unit="%",
                reset_at=reset_at,
                reset_in_sec=reset_in_sec,
            )
        )
    return windows


def filter_windows(windows: list[QuotaWindow], account: AccountConfig) -> list[QuotaWindow]:
    out: list[QuotaWindow] = []
    for window in windows:
        if window.label == LABEL_ROLLING and not account.show_rolling:
            continue
        if window.label == LABEL_WEEKLY and not account.show_weekly:
            continue
        if window.label == LABEL_MONTHLY and not account.show_monthly:
            continue
        out.append(window)
    return out


async def fetch_go_status(
    client: httpx.AsyncClient, org_id: str, cookie_header: str
) -> dict[str, Any]:
    require_console_session(cookie_header)
    resp = await client.get(
        CONSOLE_GO_STATUS_URL,
        headers=console_api_headers(cookie_header, org_id),
    )
    if resp.status_code in (401, 403):
        raise ValueError(f"认证失败 (HTTP {resp.status_code})，请检查 Console Cookie")
    if resp.status_code == 400:
        raise ValueError("缺少或无效的工作区 ID（x-org-id），请配置 wrk_...")
    if resp.status_code < 200 or resp.status_code >= 300:
        raise ValueError(f"go/status 返回 HTTP {resp.status_code}")
    return resp.json()


async def fetch_quota_for_account(account: AccountConfig, index: int) -> QuotaAccount:
    now = datetime.now(UTC)
    updated_at = now.isoformat().replace("+00:00", "Z")
    workspace_hint = (account.workspace_id or "").strip()

    if not account.auth_cookie.strip():
        return QuotaAccount(
            index=index,
            name=account.name,
            workspace_id=workspace_hint,
            success=False,
            updated_at=updated_at,
            windows=[],
            error="未配置 Console Cookie",
        )

    try:
        org_id = resolve_workspace_id(workspace_hint)
        cookie_header = build_cookie_header(account.auth_cookie)
        if not cookie_header:
            raise ValueError("Console Cookie 为空")

        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            payload = await fetch_go_status(client, org_id, cookie_header)
            windows = parse_go_status_payload(payload, now)
            if not windows:
                raise ValueError("go/status 响应中无额度 meters 数据")

            return QuotaAccount(
                index=index,
                name=account.name,
                workspace_id=org_id,
                success=True,
                updated_at=updated_at,
                windows=filter_windows(windows, account),
            )
    except Exception as exc:
        return QuotaAccount(
            index=index,
            name=account.name,
            workspace_id=workspace_hint,
            success=False,
            updated_at=updated_at,
            windows=[],
            error=str(exc),
        )


async def fetch_all_quotas(accounts: list[AccountConfig]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, account in enumerate(accounts):
        quota = await fetch_quota_for_account(account, index)
        results.append(quota.to_dict())
    return results
