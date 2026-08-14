from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from .db import CPAChannelRow
from .quota import LABEL_MONTHLY, LABEL_ROLLING, LABEL_WEEKLY
from .secrets import keyed_fingerprint
from .version import APP_VERSION

TIMEOUT = httpx.Timeout(20.0, connect=10.0)
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
USER_AGENT = f"QuotaHub/{APP_VERSION}"


class CPAError(ValueError):
    pass


class CPAChannelAuthenticationError(CPAError):
    pass


class CPAAccountAuthenticationError(CPAError):
    pass


class CPAPassiveSnapshotsUnsupported(CPAError):
    pass


@dataclass
class CPAAuthAccount:
    auth_index: str
    auth_file_name: str
    account_key_hash: str
    account_display: str
    plan: str
    legacy_account_key_hash: str | None = None
    previous_account_key_hash: str | None = None


@dataclass
class CPAAccountQuota:
    plan: str
    windows: list[dict[str, Any]]

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.windows[index]


@dataclass
class CPAHeaderSnapshotQuota:
    plan: str
    windows: list[dict[str, Any]]
    observed_at: str


def normalize_cpa_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("CPA URL 不能为空")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("CPA URL 必须是有效的 http/https 地址")
    if parsed.username or parsed.password:
        raise ValueError("CPA URL 不能包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("CPA URL 不能包含查询参数或片段")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", ""))


def _management_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _management_headers(key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }


def mask_cpa_account(value: str) -> str:
    text = value.strip()
    if not text:
        return "未知账号"
    if "@" in text:
        local, domain = text.rsplit("@", 1)
        if domain:
            edge = local[:1] or "*"
            return f"{edge}***@{domain}"
    if len(text) <= 4:
        return f"{text[:1]}***"
    if len(text) <= 8:
        return f"{text[:1]}***{text[-1:]}"
    return f"{text[:2]}***{text[-2:]}"


def map_cpa_plan(value: Any) -> str:
    raw = str(value or "").strip().lower()
    compact = re.sub(r"[\s_-]+", "", raw)
    if compact == "free" or compact.startswith("free"):
        return "Free"
    if compact == "plus" or compact.startswith("plus"):
        return "Plus"
    if compact in {"prolite", "5x", "pro5x"} or "prolite" in compact or "5x" in compact:
        return "Pro 5x"
    if compact in {"pro", "20x", "pro20x"} or "20x" in compact:
        return "Pro 20x"
    return "未知套餐"


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _nested_text(data: Any, keys: set[str], *, max_depth: int = 5) -> str:
    queue: list[tuple[Any, int]] = [(data, 0)]
    while queue:
        value, depth = queue.pop(0)
        if depth > max_depth:
            continue
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in keys and isinstance(item, str) and item.strip():
                    return item.strip()
                if isinstance(item, (dict, list)):
                    queue.append((item, depth + 1))
        elif isinstance(value, list):
            queue.extend((item, depth + 1) for item in value)
    return ""


def _ordered_nested_text(data: Any, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _nested_text(data, {key})
        if value:
            return value
    return ""


def _resolve_cpa_plan(entry: dict[str, Any]) -> str:
    candidates = [
        _ordered_nested_text(
            entry.get("id_token"), ("plan_type", "chatgpt_plan_type")
        ),
        _first_text(entry, ("plan_type", "chatgpt_plan_type")),
        _ordered_nested_text(entry.get("id_token"), ("plan",)),
        _first_text(entry, ("plan",)),
        _ordered_nested_text(entry.get("id_token"), ("account_type",)),
        _first_text(entry, ("account_type",)),
    ]
    for candidate in candidates:
        mapped = map_cpa_plan(candidate)
        if mapped != "未知套餐":
            return mapped
    return "未知套餐"


def _account_from_auth_file(entry: dict[str, Any]) -> CPAAuthAccount | None:
    provider = _first_text(entry, ("provider", "type")).lower()
    if provider != "codex":
        return None
    status = str(entry.get("status") or "").strip().lower()
    if bool(entry.get("disabled")) or bool(entry.get("unavailable")) or status == "disabled":
        return None
    auth_index = _first_text(entry, ("auth_index", "authIndex", "AuthIndex"))
    if not auth_index:
        return None
    auth_file_name = _first_text(entry, ("name", "file_name", "fileName", "filename"))

    email = _first_text(entry, ("email",))
    account = _first_text(entry, ("account",))
    account_id = _ordered_nested_text(
        entry.get("id_token"),
        ("chatgpt_account_id", "chatgptaccountid", "account_id"),
    )
    display_source = email or account or account_id
    if display_source:
        display = mask_cpa_account(display_source)
    else:
        display = "未知账号"

    if account_id:
        subject = f"chatgpt_account_id\x00{account_id.strip().casefold()}"
    elif account:
        subject = f"account\x00{account.strip().casefold()}"
    elif email:
        subject = f"email\x00{email.strip().casefold()}"
    elif auth_file_name:
        subject = f"auth_file_name\x00{auth_file_name.strip().casefold()}"
    else:
        subject = "identity_unavailable"
    identity_material = f"{auth_index.strip()}\x00{subject}"

    return CPAAuthAccount(
        auth_index=auth_index,
        auth_file_name=auth_file_name,
        account_key_hash=keyed_fingerprint("cpa-account-v2", identity_material),
        account_display=display,
        plan=_resolve_cpa_plan(entry),
        legacy_account_key_hash=hashlib.sha256(auth_index.encode("utf-8")).hexdigest(),
        previous_account_key_hash=keyed_fingerprint("cpa-account", auth_index),
    )


def parse_auth_files(payload: Any) -> list[CPAAuthAccount]:
    if not isinstance(payload, dict):
        raise CPAError("CPA 账号列表响应格式无效")
    files = payload.get("files")
    if not isinstance(files, list):
        raise CPAError("CPA 账号列表缺少 files")
    accounts: list[CPAAuthAccount] = []
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            continue
        account = _account_from_auth_file(item)
        if account is None or account.account_key_hash in seen:
            continue
        seen.add(account.account_key_hash)
        accounts.append(account)
    return accounts


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def _number_from(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        number = _as_number(data.get(key))
        if number is not None:
            return number
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    numeric = _as_number(text)
    if numeric is not None and re.fullmatch(r"\d+(?:\.\d+)?", text):
        return _parse_timestamp(numeric)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _window_label(key: str, duration_sec: int | None) -> str:
    normalized = key.lower().replace("_window", "")
    if "month" in normalized:
        return LABEL_MONTHLY
    if "week" in normalized or "secondary" in normalized:
        if duration_sec is None or duration_sec <= 10 * 24 * 3600:
            return LABEL_WEEKLY
    if duration_sec is not None:
        if duration_sec <= 6 * 3600:
            return LABEL_ROLLING
        if duration_sec <= 10 * 24 * 3600:
            return LABEL_WEEKLY
        return LABEL_MONTHLY
    return LABEL_ROLLING if "primary" in normalized else LABEL_WEEKLY


def _normalize_quota_window(
    key: str, raw: dict[str, Any], now: datetime
) -> dict[str, Any] | None:
    used = _number_from(
        raw,
        ("used_percent", "usedPercent", "usage_percent", "usagePercent", "percent_used"),
    )
    if used is None:
        remaining = _number_from(raw, ("remaining_percent", "remainingPercent"))
        if remaining is not None:
            used = 100.0 - remaining
    if used is None:
        return None
    used = max(0.0, min(100.0, used))

    duration_number = _number_from(
        raw,
        (
            "limit_window_seconds",
            "limitWindowSeconds",
            "window_seconds",
            "windowSeconds",
            "duration_seconds",
            "durationSeconds",
        ),
    )
    if duration_number is None:
        duration_minutes = _number_from(raw, ("window_minutes", "windowMinutes"))
        if duration_minutes is not None:
            duration_number = duration_minutes * 60
    duration_sec = max(0, int(duration_number)) if duration_number is not None else None
    reset_number = _number_from(
        raw,
        (
            "reset_after_seconds",
            "resetAfterSeconds",
            "reset_in_sec",
            "resetInSec",
            "reset_seconds",
        ),
    )
    reset_in_sec = max(0, int(reset_number)) if reset_number is not None else 0
    reset_at_value = next(
        (
            raw.get(name)
            for name in (
                "reset_at",
                "resetAt",
                "reset_at_ms",
                "resetAtMs",
                "reset_time",
                "resetTime",
            )
            if raw.get(name) is not None
        ),
        None,
    )
    reset_at_dt = _parse_timestamp(reset_at_value)
    if reset_at_dt is None and reset_in_sec:
        reset_at_dt = now + timedelta(seconds=reset_in_sec)
    if reset_at_dt is not None and not reset_in_sec:
        reset_in_sec = max(0, int((reset_at_dt - now).total_seconds()))

    payload: dict[str, Any] = {
        "label": _window_label(key, duration_sec),
        "used": round(used, 2),
        "remaining": round(100.0 - used, 2),
        "total": 100.0,
        "unit": "%",
        "reset_at": reset_at_dt.isoformat().replace("+00:00", "Z") if reset_at_dt else "",
        "reset_in_sec": reset_in_sec,
    }
    if duration_sec is not None:
        payload["duration_sec"] = duration_sec
    return payload


def _quota_container(payload: Any) -> dict[str, Any] | None:
    queue: list[tuple[Any, int]] = [(payload, 0)]
    window_keys = {
        "primary",
        "secondary",
        "primary_window",
        "secondary_window",
        "weekly",
        "monthly",
    }
    while queue:
        value, depth = queue.pop(0)
        if depth > 6:
            continue
        if isinstance(value, dict):
            if any(key in value and isinstance(value[key], dict) for key in window_keys):
                return value
            for key in ("items", "response_metadata", "quota", "rate_limit", "rateLimit"):
                nested = value.get(key)
                if isinstance(nested, (dict, list)):
                    queue.append((nested, depth + 1))
        elif isinstance(value, list):
            queue.extend((item, depth + 1) for item in value[:10])
    return None


def parse_cpa_usage_payload(payload: Any, *, now: datetime | None = None) -> list[dict[str, Any]]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CPAError("CPA 额度响应不是有效 JSON") from exc
    container = _quota_container(payload)
    if container is None:
        raise CPAError("CPA 额度响应缺少 quota 窗口")
    current = now or datetime.now(UTC)
    windows: list[dict[str, Any]] = []
    for key in (
        "primary",
        "primary_window",
        "secondary",
        "secondary_window",
        "weekly",
        "monthly",
    ):
        raw = container.get(key)
        if not isinstance(raw, dict):
            continue
        window = _normalize_quota_window(key, raw, current)
        if window is not None and not any(item["label"] == window["label"] for item in windows):
            windows.append(window)
    if not windows:
        raise CPAError("CPA 额度响应无法解析窗口数据")
    order = {LABEL_ROLLING: 0, LABEL_WEEKLY: 1, LABEL_MONTHLY: 2}
    windows.sort(key=lambda item: order.get(str(item.get("label")), 99))
    return windows


def parse_cpa_account_quota(
    payload: Any, *, now: datetime | None = None
) -> CPAAccountQuota:
    decoded = payload
    if isinstance(decoded, str):
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise CPAError("CPA 额度响应不是有效 JSON") from exc
    container = _quota_container(decoded)
    if container is None:
        raise CPAError("CPA 额度响应缺少 quota 窗口")
    plan_candidates = [
        _first_text(container, ("plan_type", "chatgpt_plan_type", "plan")),
        _first_text(decoded, ("plan_type", "chatgpt_plan_type", "plan"))
        if isinstance(decoded, dict)
        else "",
    ]
    plan = "未知套餐"
    for candidate in plan_candidates:
        mapped = map_cpa_plan(candidate)
        if mapped != "未知套餐":
            plan = mapped
            break
    return CPAAccountQuota(
        plan=plan,
        windows=parse_cpa_usage_payload(decoded, now=now),
    )


def _normalized_snapshot_identity(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        return ""
    return str(value).strip().casefold()


def match_cpa_header_snapshot(
    account: CPAAuthAccount, items: list[Any]
) -> dict[str, Any] | None:
    file_name = _normalized_snapshot_identity(account.auth_file_name)
    auth_index = _normalized_snapshot_identity(account.auth_index)
    if not file_name or not auth_index:
        return None

    newest: dict[str, Any] | None = None
    newest_timestamp = float("-inf")
    for item in items:
        if not isinstance(item, dict):
            continue
        if _normalized_snapshot_identity(item.get("auth_file_snapshot")) != file_name:
            continue
        if _normalized_snapshot_identity(item.get("auth_index")) != auth_index:
            continue
        timestamp = _as_number(item.get("timestamp_ms"))
        if timestamp is None or timestamp < newest_timestamp:
            continue
        newest = item
        newest_timestamp = timestamp
    return newest


def parse_cpa_header_snapshot(
    snapshot: Any, *, now: datetime | None = None
) -> CPAHeaderSnapshotQuota:
    if not isinstance(snapshot, dict):
        raise CPAError("CPA Header Snapshot 格式无效")
    observed = _parse_timestamp(snapshot.get("timestamp_ms"))
    if observed is None:
        raise CPAError("CPA Header Snapshot 缺少有效观测时间")
    metadata = snapshot.get("response_metadata")
    quota = metadata.get("quota") if isinstance(metadata, dict) else None
    if not isinstance(quota, dict):
        raise CPAError("CPA Header Snapshot 缺少 quota")

    windows = parse_cpa_usage_payload({"quota": quota}, now=observed)
    plan = map_cpa_plan(snapshot.get("header_quota_plan_type"))
    if plan == "未知套餐":
        plan = map_cpa_plan(quota.get("plan_type"))
    return CPAHeaderSnapshotQuota(
        plan=plan,
        windows=windows,
        observed_at=observed.isoformat().replace("+00:00", "Z"),
    )


async def discover_cpa_accounts(
    channel: CPAChannelRow, client: httpx.AsyncClient | None = None
) -> list[CPAAuthAccount]:
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False)
    try:
        response = await http.get(
            _management_url(channel.base_url, "/v0/management/auth-files"),
            headers=_management_headers(channel.management_key),
        )
        if response.status_code in (401, 403):
            raise CPAChannelAuthenticationError("CPA 管理认证失败")
        if response.status_code < 200 or response.status_code >= 300:
            raise CPAError(f"CPA 账号发现返回 HTTP {response.status_code}")
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise CPAError("CPA 账号列表响应不是有效 JSON") from exc
        return parse_auth_files(payload)
    finally:
        if owns_client:
            await http.aclose()


async def fetch_cpa_header_snapshots(
    channel: CPAChannelRow, client: httpx.AsyncClient | None = None
) -> list[dict[str, Any]]:
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False)
    try:
        response = await http.get(
            _management_url(
                channel.base_url, "/v0/management/monitoring/header-snapshots"
            ),
            headers=_management_headers(channel.management_key),
            params={"days": 30, "limit": 1000},
        )
        if response.status_code in (401, 403):
            raise CPAChannelAuthenticationError("CPA 管理认证失败")
        if response.status_code in (404, 405):
            raise CPAPassiveSnapshotsUnsupported("CPA 不支持 Header Snapshot")
        if response.status_code < 200 or response.status_code >= 300:
            raise CPAError(f"CPA Header Snapshot 返回 HTTP {response.status_code}")
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise CPAError("CPA Header Snapshot 响应不是有效 JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise CPAError("CPA Header Snapshot 响应缺少 items")
        return [item for item in payload["items"] if isinstance(item, dict)]
    finally:
        if owns_client:
            await http.aclose()


async def fetch_cpa_account_quota(
    channel: CPAChannelRow,
    account: CPAAuthAccount,
    client: httpx.AsyncClient | None = None,
) -> CPAAccountQuota:
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False)
    try:
        response = await http.post(
            _management_url(channel.base_url, "/v0/management/api-call"),
            headers={**_management_headers(channel.management_key), "Content-Type": "application/json"},
            json={
                "auth_index": account.auth_index,
                "method": "GET",
                "url": USAGE_URL,
                "header": {
                    "Authorization": "Bearer $TOKEN$",
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            },
        )
        if response.status_code in (401, 403):
            raise CPAChannelAuthenticationError("CPA 管理认证失败")
        if response.status_code < 200 or response.status_code >= 300:
            raise CPAError(f"CPA 代理调用返回 HTTP {response.status_code}")
        try:
            wrapper = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise CPAError("CPA 代理调用响应不是有效 JSON") from exc
        if not isinstance(wrapper, dict):
            raise CPAError("CPA 代理调用响应格式无效")
        try:
            status_code = int(wrapper.get("status_code") or 0)
        except (TypeError, ValueError) as exc:
            raise CPAError("CPA 代理调用缺少有效状态码") from exc
        if status_code in (401, 403):
            raise CPAAccountAuthenticationError("CPA 账号认证失败")
        if status_code < 200 or status_code >= 300:
            raise CPAError(f"CPA 上游额度返回 HTTP {status_code or '未知'}")
        return parse_cpa_account_quota(wrapper.get("body"))
    finally:
        if owns_client:
            await http.aclose()
