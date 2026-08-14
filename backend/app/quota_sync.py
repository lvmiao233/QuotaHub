from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import httpx

from . import db
from .config import AccountConfig, OllamaAccountConfig, load_service_config
from .cpa_quota import (
    CPAAccountQuota,
    CPAAccountAuthenticationError,
    CPAChannelAuthenticationError,
    CPAError,
    CPAPassiveSnapshotsUnsupported,
    TIMEOUT as CPA_TIMEOUT,
    discover_cpa_accounts,
    fetch_cpa_account_quota,
    fetch_cpa_header_snapshots,
    match_cpa_header_snapshot,
    parse_cpa_header_snapshot,
)
from .ollama_quota import fetch_ollama_quota_for_account
from .quota import fetch_quota_for_account
from .logging_config import get_logger, log_event, safe_exception_fields
from .scheduler import SchedulerLease

POLL_SECONDS = 30
REQUEST_PACING_SECONDS = 1.0
QUOTA_LEASE_NAME = "quota-collection"
CPA_ACTIVE_FALLBACK_INTERVAL_SECONDS = 12 * 60 * 60
CPA_PASSIVE_SNAPSHOT_MAX_AGE = timedelta(hours=6)
CPA_PASSIVE_SNAPSHOT_FUTURE_TOLERANCE = timedelta(minutes=5)

_collection_lock = asyncio.Lock()
_wakeup = asyncio.Event()
logger = get_logger("quota_sync")

LeaseCheck = Callable[[], bool]


class QuotaCollectionInterrupted(RuntimeError):
    pass


def _require_lease(lease_check: LeaseCheck | None) -> None:
    if lease_check is not None and not lease_check():
        raise QuotaCollectionInterrupted("scheduler lease lost")


def _run_fields(run_id: str | None) -> dict[str, str]:
    return {"run_id": run_id} if run_id else {}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_due(last_attempt_at: str | None, interval_sec: int) -> bool:
    if not last_attempt_at:
        return True
    return (datetime.now(UTC) - _parse_time(last_attempt_at)).total_seconds() >= interval_sec


def _is_fresh_cpa_observation(observed_at: str) -> bool:
    try:
        observed = _parse_time(observed_at)
        age = datetime.now(UTC) - observed
    except (TypeError, ValueError):
        return False
    return (
        -CPA_PASSIVE_SNAPSHOT_FUTURE_TOLERANCE
        <= age
        <= CPA_PASSIVE_SNAPSHOT_MAX_AGE
    )


def _safe_error(value: Any) -> str:
    text = str(value or "")
    if "认证失败" in text or "未登录" in text:
        return "认证失败，请检查账号凭证"
    if "未配置" in text or "为空" in text:
        return "账号凭证未配置"
    return "额度采集失败"


def _safe_cpa_error(value: Any) -> str:
    if isinstance(value, CPAChannelAuthenticationError):
        return "CPA 管理认证失败，请检查管理密钥"
    if isinstance(value, CPAAccountAuthenticationError):
        return "CPA 账号认证失败"
    return "CPA 额度采集失败"


def _current_opencode_account(
    original: db.OpenCodeAccountRow,
) -> db.OpenCodeAccountRow | None:
    current = db.get_opencode_account(original.id)
    if (
        current is None
        or not current.enabled
        or current.collection_revision != original.collection_revision
        or current.auth_cookie != original.auth_cookie
        or current.workspace_id != original.workspace_id
    ):
        return None
    return current


def _current_ollama_account(original: db.OllamaAccountRow) -> db.OllamaAccountRow | None:
    current = db.get_ollama_account(original.id)
    if (
        current is None
        or not current.enabled
        or current.collection_revision != original.collection_revision
        or current.session_cookie != original.session_cookie
    ):
        return None
    return current


def _current_cpa_channel(original: db.CPAChannelRow) -> db.CPAChannelRow | None:
    current = db.get_cpa_channel(original.id)
    if (
        current is None
        or not current.enabled
        or current.collection_revision != original.collection_revision
        or current.base_url != original.base_url
        or current.management_key != original.management_key
    ):
        return None
    return current


async def collect_opencode_account(
    account: db.OpenCodeAccountRow,
    *,
    lease_check: LeaseCheck | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
    run_id: str | None = None,
) -> bool:
    started_at = time.monotonic()
    config = AccountConfig(
        name=account.name,
        workspace_id=account.workspace_id,
        auth_cookie=account.auth_cookie,
        show_rolling=account.show_rolling,
        show_weekly=account.show_weekly,
        show_monthly=account.show_monthly,
    )
    try:
        _require_lease(lease_check)
        result = await fetch_quota_for_account(config, 0)
        _require_lease(lease_check)
        if _current_opencode_account(account) is None:
            log_event(
                logger,
                logging.WARNING,
                "quota_result_discarded",
                provider="opencode",
                account_id=account.id,
                reason="source_deleted_disabled_or_changed",
                **_run_fields(run_id),
            )
            return False
        payload = result.to_dict()
        success = bool(payload.get("success"))
        windows = payload.get("windows") or []
        _require_lease(lease_check)
        db.record_opencode_quota_snapshot(
            account.id,
            success=success,
            windows=windows,
            error=None if success else _safe_error(payload.get("error")),
            expected_collection_revision=account.collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        log_event(
            logger,
            logging.INFO if success else logging.WARNING,
            "quota_job_completed" if success else "quota_job_failed",
            provider="opencode",
            account_id=account.id,
            windows_count=len(windows),
            duration_ms=round((time.monotonic() - started_at) * 1000),
            **({} if success else {"error_code": "upstream_quota_error"}),
            **_run_fields(run_id),
        )
        return success
    except db.CollectionGuardRejected as exc:
        if exc.reason == "lease_lost":
            log_event(
                logger,
                logging.WARNING,
                "quota_job_interrupted",
                provider="opencode",
                account_id=account.id,
                reason="lease_lost",
                **_run_fields(run_id),
            )
            raise QuotaCollectionInterrupted("scheduler lease lost") from exc
        log_event(
            logger,
            logging.WARNING,
            "quota_result_discarded",
            provider="opencode",
            account_id=account.id,
            reason="source_deleted_disabled_or_changed",
            **_run_fields(run_id),
        )
        return False
    except QuotaCollectionInterrupted:
        log_event(
            logger,
            logging.WARNING,
            "quota_job_interrupted",
            provider="opencode",
            account_id=account.id,
            reason="lease_lost",
            **_run_fields(run_id),
        )
        raise
    except Exception as exc:
        _require_lease(lease_check)
        if _current_opencode_account(account) is None:
            log_event(
                logger,
                logging.WARNING,
                "quota_result_discarded",
                provider="opencode",
                account_id=account.id,
                reason="source_deleted_disabled_or_changed",
                **_run_fields(run_id),
            )
            return False
        try:
            db.record_opencode_quota_snapshot(
                account.id,
                success=False,
                error=_safe_error(exc),
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
            )
        except db.CollectionGuardRejected as guard_exc:
            if guard_exc.reason == "lease_lost":
                log_event(
                    logger,
                    logging.WARNING,
                    "quota_job_interrupted",
                    provider="opencode",
                    account_id=account.id,
                    reason="lease_lost",
                    **_run_fields(run_id),
                )
                raise QuotaCollectionInterrupted("scheduler lease lost") from guard_exc
            log_event(
                logger,
                logging.WARNING,
                "quota_result_discarded",
                provider="opencode",
                account_id=account.id,
                reason="source_deleted_disabled_or_changed",
                **_run_fields(run_id),
            )
            return False
        log_event(
            logger,
            logging.WARNING,
            "quota_job_failed",
            provider="opencode",
            account_id=account.id,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            **safe_exception_fields(exc, "collection_error"),
            **_run_fields(run_id),
        )
        return False


async def collect_ollama_account(
    account: db.OllamaAccountRow,
    *,
    lease_check: LeaseCheck | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
    run_id: str | None = None,
) -> bool:
    started_at = time.monotonic()
    config = OllamaAccountConfig(
        name=account.name,
        session_cookie=account.session_cookie,
        show_session=account.show_session,
        show_weekly=account.show_weekly,
    )
    try:
        _require_lease(lease_check)
        result = await fetch_ollama_quota_for_account(config, 0)
        _require_lease(lease_check)
        if _current_ollama_account(account) is None:
            log_event(
                logger,
                logging.WARNING,
                "quota_result_discarded",
                provider="ollama",
                account_id=account.id,
                reason="source_deleted_disabled_or_changed",
                **_run_fields(run_id),
            )
            return False
        payload = result.to_dict()
        success = bool(payload.get("success"))
        windows = payload.get("windows") or []
        _require_lease(lease_check)
        db.record_ollama_quota_snapshot(
            account.id,
            success=success,
            plan=str(payload.get("plan") or "") or None,
            windows=windows,
            error=None if success else _safe_error(payload.get("error")),
            expected_collection_revision=account.collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        log_event(
            logger,
            logging.INFO if success else logging.WARNING,
            "quota_job_completed" if success else "quota_job_failed",
            provider="ollama",
            account_id=account.id,
            windows_count=len(windows),
            duration_ms=round((time.monotonic() - started_at) * 1000),
            **({} if success else {"error_code": "upstream_quota_error"}),
            **_run_fields(run_id),
        )
        return success
    except db.CollectionGuardRejected as exc:
        if exc.reason == "lease_lost":
            log_event(
                logger,
                logging.WARNING,
                "quota_job_interrupted",
                provider="ollama",
                account_id=account.id,
                reason="lease_lost",
                **_run_fields(run_id),
            )
            raise QuotaCollectionInterrupted("scheduler lease lost") from exc
        log_event(
            logger,
            logging.WARNING,
            "quota_result_discarded",
            provider="ollama",
            account_id=account.id,
            reason="source_deleted_disabled_or_changed",
            **_run_fields(run_id),
        )
        return False
    except QuotaCollectionInterrupted:
        log_event(
            logger,
            logging.WARNING,
            "quota_job_interrupted",
            provider="ollama",
            account_id=account.id,
            reason="lease_lost",
            **_run_fields(run_id),
        )
        raise
    except Exception as exc:
        _require_lease(lease_check)
        if _current_ollama_account(account) is None:
            log_event(
                logger,
                logging.WARNING,
                "quota_result_discarded",
                provider="ollama",
                account_id=account.id,
                reason="source_deleted_disabled_or_changed",
                **_run_fields(run_id),
            )
            return False
        try:
            db.record_ollama_quota_snapshot(
                account.id,
                success=False,
                error=_safe_error(exc),
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
            )
        except db.CollectionGuardRejected as guard_exc:
            if guard_exc.reason == "lease_lost":
                log_event(
                    logger,
                    logging.WARNING,
                    "quota_job_interrupted",
                    provider="ollama",
                    account_id=account.id,
                    reason="lease_lost",
                    **_run_fields(run_id),
                )
                raise QuotaCollectionInterrupted("scheduler lease lost") from guard_exc
            log_event(
                logger,
                logging.WARNING,
                "quota_result_discarded",
                provider="ollama",
                account_id=account.id,
                reason="source_deleted_disabled_or_changed",
                **_run_fields(run_id),
            )
            return False
        log_event(
            logger,
            logging.WARNING,
            "quota_job_failed",
            provider="ollama",
            account_id=account.id,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            **safe_exception_fields(exc, "collection_error"),
            **_run_fields(run_id),
        )
        return False


async def collect_cpa_channel(
    channel: db.CPAChannelRow,
    *,
    lease_check: LeaseCheck | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
    run_id: str | None = None,
) -> bool:
    started_at = time.monotonic()
    success_count = 0
    failure_count = 0
    try:
        _require_lease(lease_check)
        async with httpx.AsyncClient(timeout=CPA_TIMEOUT, follow_redirects=False) as client:
            accounts = await discover_cpa_accounts(channel, client)
            _require_lease(lease_check)
            current = _current_cpa_channel(channel)
            if current is None:
                log_event(
                    logger,
                    logging.WARNING,
                    "quota_result_discarded",
                    provider="cpa",
                    channel_id=channel.id,
                    reason="source_deleted_disabled_or_changed",
                    **_run_fields(run_id),
                )
                return False

            passive_snapshots: list[dict[str, Any]] = []
            try:
                _require_lease(lease_check)
                passive_snapshots = await fetch_cpa_header_snapshots(
                    current, client
                )
                _require_lease(lease_check)
                if _current_cpa_channel(channel) is None:
                    log_event(
                        logger,
                        logging.WARNING,
                        "quota_result_discarded",
                        provider="cpa",
                        channel_id=channel.id,
                        reason="source_deleted_disabled_or_changed",
                        **_run_fields(run_id),
                    )
                    return False
                log_event(
                    logger,
                    logging.INFO,
                    "cpa_passive_snapshots_loaded",
                    provider="cpa",
                    channel_id=channel.id,
                    snapshot_count=len(passive_snapshots),
                    **_run_fields(run_id),
                )
            except CPAPassiveSnapshotsUnsupported:
                log_event(
                    logger,
                    logging.INFO,
                    "cpa_passive_snapshots_unsupported",
                    provider="cpa",
                    channel_id=channel.id,
                    **_run_fields(run_id),
                )
            except CPAChannelAuthenticationError:
                raise
            except QuotaCollectionInterrupted:
                raise
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "cpa_passive_snapshots_failed",
                    provider="cpa",
                    channel_id=channel.id,
                    **safe_exception_fields(exc, "passive_snapshot_error"),
                    **_run_fields(run_id),
                )

            _require_lease(lease_check)
            db.prepare_cpa_channel_discovery(
                channel.id,
                [
                    (
                        account.account_key_hash,
                        (
                            account.previous_account_key_hash,
                            account.legacy_account_key_hash,
                        ),
                        account.account_display,
                        account.plan,
                    )
                    for account in accounts
                ],
                expected_collection_revision=channel.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
            )
            log_event(
                logger,
                logging.INFO,
                "cpa_discovery_completed",
                provider="cpa",
                channel_id=channel.id,
                accounts_discovered=len(accounts),
                **_run_fields(run_id),
            )
            active_request_count = 0
            for account in accounts:
                _require_lease(lease_check)
                current = _current_cpa_channel(channel)
                if current is None:
                    log_event(
                        logger,
                        logging.WARNING,
                        "quota_result_discarded",
                        provider="cpa",
                        channel_id=channel.id,
                        reason="source_deleted_disabled_or_changed",
                        **_run_fields(run_id),
                    )
                    return False

                matched_snapshot = match_cpa_header_snapshot(
                    account, passive_snapshots
                )
                passive_quota = None
                if matched_snapshot is not None:
                    try:
                        passive_quota = parse_cpa_header_snapshot(matched_snapshot)
                    except CPAError:
                        passive_quota = None
                if passive_quota is not None and _is_fresh_cpa_observation(
                    passive_quota.observed_at
                ):
                    _require_lease(lease_check)
                    if _current_cpa_channel(channel) is None:
                        return False
                    plan = (
                        passive_quota.plan
                        if passive_quota.plan != "未知套餐"
                        else account.plan
                    )
                    public_id = db.record_cpa_quota_snapshot(
                        channel.id,
                        account.account_key_hash,
                        account_display=account.account_display,
                        plan=plan,
                        success=True,
                        windows=passive_quota.windows,
                        quota_source="response_header",
                        observed_at=passive_quota.observed_at,
                        expected_collection_revision=channel.collection_revision,
                        lease_name=lease_name,
                        lease_owner_id=lease_owner_id,
                    )
                    success_count += 1
                    log_event(
                        logger,
                        logging.INFO,
                        "quota_job_completed",
                        provider="cpa",
                        channel_id=channel.id,
                        public_id=public_id,
                        quota_source="response_header",
                        windows_count=len(passive_quota.windows),
                        **_run_fields(run_id),
                    )
                    continue

                last_active_attempt_at = db.get_cpa_active_attempt(
                    channel.id, account.account_key_hash
                )
                if not _is_due(
                    last_active_attempt_at,
                    CPA_ACTIVE_FALLBACK_INTERVAL_SECONDS,
                ):
                    log_event(
                        logger,
                        logging.DEBUG,
                        "cpa_active_fallback_skipped",
                        provider="cpa",
                        channel_id=channel.id,
                        reason="active_fallback_throttled",
                        **_run_fields(run_id),
                    )
                    continue

                if active_request_count > 0 and REQUEST_PACING_SECONDS > 0:
                    await asyncio.sleep(REQUEST_PACING_SECONDS)
                    _require_lease(lease_check)
                active_request_count += 1
                active_attempted_at = datetime.now(UTC).isoformat().replace(
                    "+00:00", "Z"
                )
                _require_lease(lease_check)
                db.record_cpa_active_attempt(
                    channel.id,
                    account.account_key_hash,
                    account_display=account.account_display,
                    plan=account.plan,
                    attempted_at=active_attempted_at,
                    expected_collection_revision=channel.collection_revision,
                    lease_name=lease_name,
                    lease_owner_id=lease_owner_id,
                )
                try:
                    _require_lease(lease_check)
                    active_quota = await fetch_cpa_account_quota(
                        current, account, client
                    )
                    if isinstance(active_quota, CPAAccountQuota):
                        windows = active_quota.windows
                        active_plan = (
                            active_quota.plan
                            if active_quota.plan != "未知套餐"
                            else account.plan
                        )
                    else:
                        windows = active_quota
                        active_plan = account.plan
                    _require_lease(lease_check)
                    if _current_cpa_channel(channel) is None:
                        log_event(
                            logger,
                            logging.WARNING,
                            "quota_result_discarded",
                            provider="cpa",
                            channel_id=channel.id,
                            reason="source_deleted_disabled_or_changed",
                            **_run_fields(run_id),
                        )
                        return False
                    _require_lease(lease_check)
                    public_id = db.record_cpa_quota_snapshot(
                        channel.id,
                        account.account_key_hash,
                        account_display=account.account_display,
                        plan=active_plan,
                        success=True,
                        windows=windows,
                        attempted_at=active_attempted_at,
                        quota_source="active_api",
                        observed_at=active_attempted_at,
                        active_attempted=True,
                        expected_collection_revision=channel.collection_revision,
                        lease_name=lease_name,
                        lease_owner_id=lease_owner_id,
                    )
                    success_count += 1
                    log_event(
                        logger,
                        logging.INFO,
                        "quota_job_completed",
                        provider="cpa",
                        channel_id=channel.id,
                        public_id=public_id,
                        quota_source="active_api",
                        windows_count=len(windows),
                        **_run_fields(run_id),
                    )
                except CPAChannelAuthenticationError as exc:
                    _require_lease(lease_check)
                    if _current_cpa_channel(channel) is None:
                        return False
                    db.record_cpa_quota_snapshot(
                        channel.id,
                        account.account_key_hash,
                        account_display=account.account_display,
                        plan=account.plan,
                        success=False,
                        error=_safe_cpa_error(exc),
                        attempted_at=active_attempted_at,
                        active_attempted=True,
                        expected_collection_revision=channel.collection_revision,
                        lease_name=lease_name,
                        lease_owner_id=lease_owner_id,
                    )
                    db.record_cpa_channel_attempt(
                        channel.id,
                        success=False,
                        error=_safe_cpa_error(exc),
                        expected_collection_revision=channel.collection_revision,
                        lease_name=lease_name,
                        lease_owner_id=lease_owner_id,
                    )
                    log_event(
                        logger,
                        logging.WARNING,
                        "cpa_channel_authentication_failed",
                        provider="cpa",
                        channel_id=channel.id,
                        accounts_remaining=max(
                            0, len(accounts) - active_request_count
                        ),
                        **safe_exception_fields(exc, "channel_authentication_failed"),
                        **_run_fields(run_id),
                    )
                    return False
                except QuotaCollectionInterrupted:
                    raise
                except Exception as exc:
                    _require_lease(lease_check)
                    if _current_cpa_channel(channel) is None:
                        return False
                    public_id = db.record_cpa_quota_snapshot(
                        channel.id,
                        account.account_key_hash,
                        account_display=account.account_display,
                        plan=account.plan,
                        success=False,
                        error=_safe_cpa_error(exc),
                        attempted_at=active_attempted_at,
                        active_attempted=True,
                        expected_collection_revision=channel.collection_revision,
                        lease_name=lease_name,
                        lease_owner_id=lease_owner_id,
                    )
                    failure_count += 1
                    log_event(
                        logger,
                        logging.WARNING,
                        "quota_job_failed",
                        provider="cpa",
                        channel_id=channel.id,
                        public_id=public_id,
                        quota_source="active_api",
                        **safe_exception_fields(exc, "account_collection_error"),
                        **_run_fields(run_id),
                    )
            _require_lease(lease_check)
            if _current_cpa_channel(channel) is not None:
                _require_lease(lease_check)
                db.record_cpa_channel_attempt(
                    channel.id,
                    success=True,
                    expected_collection_revision=channel.collection_revision,
                    lease_name=lease_name,
                    lease_owner_id=lease_owner_id,
                )
                log_event(
                    logger,
                    logging.INFO,
                    "cpa_channel_collection_completed",
                    provider="cpa",
                    channel_id=channel.id,
                    account_count=len(accounts),
                    success_count=success_count,
                    failure_count=failure_count,
                    duration_ms=round((time.monotonic() - started_at) * 1000),
                    **_run_fields(run_id),
                )
                return True
            return False
    except db.CollectionGuardRejected as exc:
        if exc.reason == "lease_lost":
            log_event(
                logger,
                logging.WARNING,
                "quota_job_interrupted",
                provider="cpa",
                channel_id=channel.id,
                reason="lease_lost",
                **_run_fields(run_id),
            )
            raise QuotaCollectionInterrupted("scheduler lease lost") from exc
        log_event(
            logger,
            logging.WARNING,
            "quota_result_discarded",
            provider="cpa",
            channel_id=channel.id,
            reason="source_deleted_disabled_or_changed",
            **_run_fields(run_id),
        )
        return False
    except QuotaCollectionInterrupted:
        log_event(
            logger,
            logging.WARNING,
            "quota_job_interrupted",
            provider="cpa",
            channel_id=channel.id,
            reason="lease_lost",
            **_run_fields(run_id),
        )
        raise
    except Exception as exc:
        _require_lease(lease_check)
        if _current_cpa_channel(channel) is not None:
            try:
                db.record_cpa_channel_attempt(
                    channel.id,
                    success=False,
                    error=_safe_cpa_error(exc),
                    expected_collection_revision=channel.collection_revision,
                    lease_name=lease_name,
                    lease_owner_id=lease_owner_id,
                )
            except db.CollectionGuardRejected as guard_exc:
                if guard_exc.reason == "lease_lost":
                    raise QuotaCollectionInterrupted(
                        "scheduler lease lost"
                    ) from guard_exc
                log_event(
                    logger,
                    logging.WARNING,
                    "quota_result_discarded",
                    provider="cpa",
                    channel_id=channel.id,
                    reason="source_deleted_disabled_or_changed",
                    **_run_fields(run_id),
                )
                return False
        error_code = (
            "channel_authentication_failed"
            if isinstance(exc, CPAChannelAuthenticationError)
            else "channel_collection_error"
        )
        log_event(
            logger,
            logging.WARNING,
            "cpa_channel_collection_failed",
            provider="cpa",
            channel_id=channel.id,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            **safe_exception_fields(exc, error_code),
            **_run_fields(run_id),
        )
        return False


async def collect_due_quotas(*, owner_id: str | None = None) -> None:
    if _collection_lock.locked():
        log_event(
            logger,
            logging.DEBUG,
            "quota_cycle_skipped",
            scheduler=QUOTA_LEASE_NAME,
            reason="in_process_collection_active",
        )
        return
    async with _collection_lock:
        lease = SchedulerLease(
            QUOTA_LEASE_NAME, **({"owner_id": owner_id} if owner_id else {})
        )
        if not await lease.acquire():
            return
        run_id: str | None = None
        cycle_started_at = time.monotonic()
        job_count = 0
        success_count = 0
        failure_count = 0
        skipped_count = 0
        cycle_reason = "completed"
        try:
            service = load_service_config()
            jobs: list[tuple[str, Any]] = []
            if service.quota_sync_opencode_go.auto_sync:
                for account in db.list_opencode_accounts(enabled_only=True):
                    if _is_due(
                        db.get_quota_snapshot_attempt("opencode", account.id),
                        service.quota_sync_opencode_go.interval_sec,
                    ):
                        jobs.append(("opencode", account))
            if service.quota_sync_ollama.auto_sync:
                for account in db.list_ollama_accounts(enabled_only=True):
                    if _is_due(
                        db.get_quota_snapshot_attempt("ollama", account.id),
                        service.quota_sync_ollama.interval_sec,
                    ):
                        jobs.append(("ollama", account))
            for channel in db.list_cpa_channels(enabled_only=True):
                if _is_due(channel.last_attempt_at, channel.interval_sec):
                    jobs.append(("cpa", channel))

            if not jobs:
                log_event(
                    logger,
                    logging.DEBUG,
                    "quota_cycle_idle",
                    scheduler=QUOTA_LEASE_NAME,
                    owner_id=lease.owner_id,
                    job_count=0,
                )
                return

            run_id = uuid.uuid4().hex[:8]
            job_count = len(jobs)
            log_event(
                logger,
                logging.INFO,
                "quota_cycle_started",
                scheduler=QUOTA_LEASE_NAME,
                owner_id=lease.owner_id,
                run_id=run_id,
                job_count=job_count,
                opencode_jobs=sum(provider == "opencode" for provider, _ in jobs),
                ollama_jobs=sum(provider == "ollama" for provider, _ in jobs),
                cpa_jobs=sum(provider == "cpa" for provider, _ in jobs),
            )
            processed = 0
            requests_started = 0
            for provider, account in jobs:
                if not lease.is_valid():
                    cycle_reason = "lease_lost"
                    skipped_count += job_count - processed
                    return
                current = (
                    _current_opencode_account(account)
                    if provider == "opencode"
                    else _current_ollama_account(account)
                    if provider == "ollama"
                    else _current_cpa_channel(account)
                )
                if current is None:
                    skipped_count += 1
                    processed += 1
                    continue
                if requests_started > 0 and REQUEST_PACING_SECONDS > 0:
                    await asyncio.sleep(REQUEST_PACING_SECONDS)
                    if not lease.is_valid():
                        cycle_reason = "lease_lost"
                        skipped_count += job_count - processed
                        return
                requests_started += 1
                try:
                    if provider == "opencode":
                        success = await collect_opencode_account(
                            current,
                            lease_check=lease.is_valid,
                            lease_name=QUOTA_LEASE_NAME,
                            lease_owner_id=lease.owner_id,
                            run_id=run_id,
                        )
                    elif provider == "ollama":
                        success = await collect_ollama_account(
                            current,
                            lease_check=lease.is_valid,
                            lease_name=QUOTA_LEASE_NAME,
                            lease_owner_id=lease.owner_id,
                            run_id=run_id,
                        )
                    else:
                        success = await collect_cpa_channel(
                            current,
                            lease_check=lease.is_valid,
                            lease_name=QUOTA_LEASE_NAME,
                            lease_owner_id=lease.owner_id,
                            run_id=run_id,
                        )
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except QuotaCollectionInterrupted:
                    cycle_reason = "lease_lost"
                    skipped_count += job_count - processed
                    return
                except Exception as exc:
                    failure_count += 1
                    identity_fields = (
                        {"channel_id": account.id}
                        if provider == "cpa"
                        else {"account_id": account.id}
                    )
                    log_event(
                        logger,
                        logging.ERROR,
                        "quota_job_unexpected_error",
                        provider=provider,
                        run_id=run_id,
                        **identity_fields,
                        **safe_exception_fields(exc, "unexpected_job_error"),
                    )
                processed += 1
        except Exception as exc:
            cycle_reason = "unexpected_error"
            log_event(
                logger,
                logging.ERROR,
                "quota_cycle_failed",
                scheduler=QUOTA_LEASE_NAME,
                owner_id=lease.owner_id,
                **safe_exception_fields(exc, "unexpected_cycle_error"),
                **_run_fields(run_id),
            )
        finally:
            if run_id is not None:
                log_event(
                    logger,
                    logging.INFO if cycle_reason == "completed" else logging.WARNING,
                    "quota_cycle_completed",
                    scheduler=QUOTA_LEASE_NAME,
                    owner_id=lease.owner_id,
                    run_id=run_id,
                    job_count=job_count,
                    success_count=success_count,
                    failure_count=failure_count,
                    skipped_count=skipped_count,
                    duration_ms=round((time.monotonic() - cycle_started_at) * 1000),
                    reason=cycle_reason,
                )
            await lease.release()


def wake_quota_sync() -> None:
    _wakeup.set()


async def quota_sync_loop() -> None:
    log_event(
        logger,
        logging.INFO,
        "scheduler_started",
        scheduler=QUOTA_LEASE_NAME,
        poll_seconds=POLL_SECONDS,
    )
    while True:
        try:
            await collect_due_quotas()
        except asyncio.CancelledError:
            log_event(
                logger,
                logging.INFO,
                "scheduler_stopped",
                scheduler=QUOTA_LEASE_NAME,
                reason="cancelled",
            )
            raise
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "scheduler_loop_recovered",
                scheduler=QUOTA_LEASE_NAME,
                **safe_exception_fields(exc, "unexpected_loop_error"),
            )
        try:
            await asyncio.wait_for(_wakeup.wait(), timeout=POLL_SECONDS)
        except TimeoutError:
            pass
        except asyncio.CancelledError:
            log_event(
                logger,
                logging.INFO,
                "scheduler_stopped",
                scheduler=QUOTA_LEASE_NAME,
                reason="cancelled",
            )
            raise
        finally:
            _wakeup.clear()
