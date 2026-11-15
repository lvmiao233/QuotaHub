from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import MistralAccountConfig

API_BUDGET_URL = "https://api.mistral.ai/v1/billing/budget"
API_SUBSCRIPTION_URL = "https://api.mistral.ai/v1/billing/subscription"
TIMEOUT = 20.0
LABEL_MONTHLY = "Monthly"
MONTHLY_POOL_USD = 150.0


@dataclass
class MistralQuotaWindow:
    label: str
    used: float
    remaining: float
    total: float
    unit: str
    reset_at: str
    reset_in_sec: int
    status_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "label": self.label,
            "used": self.used,
            "remaining": self.remaining,
            "total": self.total,
            "unit": self.unit,
            "reset_at": self.reset_at,
            "reset_in_sec": self.reset_in_sec,
        }
        if self.status_text:
            payload["status_text"] = self.status_text
        return payload


@dataclass
class MistralQuotaAccount:
    index: int
    name: str
    success: bool
    updated_at: str
    plan: str = ""
    windows: list[MistralQuotaWindow] | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "index": self.index,
            "name": self.name,
            "success": self.success,
            "updated_at": self.updated_at,
        }
        if self.plan:
            payload["plan"] = self.plan
        if self.error:
            payload["error"] = self.error
        if self.windows:
            payload["windows"] = [w.to_dict() for w in self.windows]
        return payload


def _parse_reset_at(value: str | None, now: datetime) -> tuple[str, int]:
    if not value:
        return "", 0
    text = value.strip()
    if text.startswith("$D"):
        text = text[2:].strip()
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


def _spent_usd_from_detail(detail: dict[str, Any] | None) -> float:
    if not isinstance(detail, dict):
        return 0.0
    try:
        used_pct = float(detail.get("usage_percentage") or 0)
        initial = float(detail.get("initial_budget") or 0)
        return initial * used_pct / 100.0
    except (TypeError, ValueError):
        return 0.0


def _merged_monthly_window(
    vibe: dict[str, Any],
    api_budget: dict[str, Any] | None,
    now: datetime,
    *,
    pool_usd: float = MONTHLY_POOL_USD,
) -> MistralQuotaWindow:
    vibe_spend = _spent_usd_from_detail(vibe)
    api_spend = _spent_usd_from_detail(api_budget)
    total_spend = vibe_spend + api_spend
    if pool_usd <= 0:
        raise ValueError("月额度池配置无效")
    used = _clamp_percent(total_spend / pool_usd * 100.0)
    reset_at, reset_in_sec = _parse_reset_at(vibe.get("reset_at"), now)
    return MistralQuotaWindow(
        label=LABEL_MONTHLY,
        used=used,
        remaining=100.0 - used,
        total=100.0,
        unit="%",
        reset_at=reset_at,
        reset_in_sec=reset_in_sec,
    )


def parse_mistral_public_budget_payload(
    payload: dict[str, Any], now: datetime
) -> list[MistralQuotaWindow]:
    vibe = payload.get("vibe_budget")
    if not isinstance(vibe, dict):
        raise ValueError("响应缺少 vibe_budget（请确认 API Key 有组织用量权限）")
    api_budget = payload.get("api_budget")
    if not isinstance(api_budget, dict):
        api_budget = None
    return [_merged_monthly_window(vibe, api_budget, now)]


async def _fetch_plan_name(client: httpx.AsyncClient, api_key: str) -> str:
    resp = await client.get(
        API_SUBSCRIPTION_URL,
        headers={"x-api-key": api_key, "Accept": "application/json"},
    )
    if resp.status_code != 200:
        return ""
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return ""
    if isinstance(data, dict):
        plan = data.get("plan_name")
        if isinstance(plan, str):
            return plan.strip()
    return ""


async def fetch_mistral_budget_via_api_key(
    client: httpx.AsyncClient, api_key: str
) -> tuple[str, list[MistralQuotaWindow]]:
    resp = await client.get(
        API_BUDGET_URL,
        headers={"x-api-key": api_key, "Accept": "application/json"},
    )
    if resp.status_code == 401:
        raise ValueError("API Key 无效或已撤销")
    if resp.status_code == 403:
        raise ValueError("该 API Key 无用量查看权限（需要 see_org_inference_usage）")
    if resp.status_code < 200 or resp.status_code >= 300:
        raise ValueError(f"/v1/billing/budget 返回 HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        raise ValueError(f"无法解析 budget JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("budget 响应不是 JSON 对象")

    now = datetime.now(UTC)
    windows = parse_mistral_public_budget_payload(payload, now)
    plan = await _fetch_plan_name(client, api_key)
    return plan, windows


async def fetch_mistral_quota_for_account(
    account: MistralAccountConfig, index: int
) -> MistralQuotaAccount:
    now = datetime.now(UTC)
    updated_at = now.isoformat().replace("+00:00", "Z")

    api_key = account.api_key.strip()
    if not api_key:
        return MistralQuotaAccount(
            index=index,
            name=account.name,
            success=False,
            updated_at=updated_at,
            error="未配置 API Key",
        )

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            plan, windows = await fetch_mistral_budget_via_api_key(client, api_key)
            filtered = [w for w in windows if account.show_monthly or w.label != LABEL_MONTHLY]
            if not filtered:
                raise ValueError("未启用任何额度窗口")

            return MistralQuotaAccount(
                index=index,
                name=account.name,
                success=True,
                updated_at=updated_at,
                plan=plan,
                windows=filtered,
            )
    except Exception as exc:
        return MistralQuotaAccount(
            index=index,
            name=account.name,
            success=False,
            updated_at=updated_at,
            error=str(exc),
        )


async def fetch_all_mistral_quotas(accounts: list[MistralAccountConfig]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, account in enumerate(accounts):
        quota = await fetch_mistral_quota_for_account(account, index)
        results.append(quota.to_dict())
    return results