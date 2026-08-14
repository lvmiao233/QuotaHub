from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from . import db
from .auth import (
    apply_login_attempt,
    client_fingerprint,
    clear_session_cookies,
    create_session,
    delete_session,
    require_admin,
    require_csrf,
    verify_admin_token,
)
from .bootstrap import ensure_bootstrapped
from .analytics import build_overview
from .config import load_service_config, mask_cookie, mask_ollama_cookie, update_service_config
from .cpa_quota import normalize_cpa_url
from .opencode_usage import resolve_account_workspace_id
from .quota_sync import quota_sync_loop, wake_quota_sync
from .logging_config import configure_logging, get_logger, log_event, safe_exception_fields
from .scheduler import SchedulerLease
from .schemas import (
    AdminLogin,
    CPAChannelCreate,
    CPAChannelUpdate,
    OllamaAccountCreate,
    OllamaAccountUpdate,
    OpenCodeAccountCreate,
    OpenCodeAccountUpdate,
    ServiceConfigUpdate,
)
from .usage_sync import UsageSyncInterrupted, backfill_usage, sync_usage_incremental
from .version import APP_VERSION

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

_sync_task: asyncio.Task[None] | None = None
_quota_task: asyncio.Task[None] | None = None
_usage_sync_lock = asyncio.Lock()
USAGE_SYNC_LEASE_NAME = "usage-record-sync"
logger = get_logger("main")


async def restart_usage_sync_task() -> None:
    global _sync_task
    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
        _sync_task = None
    service = load_service_config()
    if service.usage_sync.auto_sync:
        _sync_task = asyncio.create_task(_usage_auto_sync_loop())
        log_event(
            logger,
            logging.INFO,
            "scheduler_restarted",
            scheduler=USAGE_SYNC_LEASE_NAME,
            interval_sec=service.usage_sync.interval_sec,
        )


def _usage_sync_due(last_sync_at: str | None, interval_sec: int) -> bool:
    if not last_sync_at:
        return True
    last = datetime.fromisoformat(last_sync_at.replace("Z", "+00:00"))
    return (datetime.now(UTC) - last).total_seconds() >= interval_sec


async def _sync_due_usage_accounts(*, owner_id: str | None = None) -> None:
    if _usage_sync_lock.locked():
        log_event(
            logger,
            logging.DEBUG,
            "usage_cycle_skipped",
            scheduler=USAGE_SYNC_LEASE_NAME,
            reason="in_process_sync_active",
        )
        return
    async with _usage_sync_lock:
        lease = SchedulerLease(
            USAGE_SYNC_LEASE_NAME, **({"owner_id": owner_id} if owner_id else {})
        )
        if not await lease.acquire():
            return
        run_id: str | None = None
        cycle_started_at = time.monotonic()
        account_count = 0
        success_count = 0
        failure_count = 0
        skipped_count = 0
        cycle_reason = "completed"
        try:
            service = load_service_config()
            settings = service.usage_sync
            if not settings.auto_sync:
                log_event(
                    logger,
                    logging.DEBUG,
                    "usage_cycle_skipped",
                    scheduler=USAGE_SYNC_LEASE_NAME,
                    owner_id=lease.owner_id,
                    reason="disabled",
                )
                return
            due_accounts: list[db.OpenCodeAccountRow] = []
            for account in db.list_opencode_accounts(enabled_only=True):
                state = db.get_usage_sync_state(account.id)
                if _usage_sync_due(state.last_sync_at, settings.interval_sec):
                    due_accounts.append(account)
            if not due_accounts:
                log_event(
                    logger,
                    logging.DEBUG,
                    "usage_cycle_idle",
                    scheduler=USAGE_SYNC_LEASE_NAME,
                    owner_id=lease.owner_id,
                    account_count=0,
                )
                return

            run_id = uuid.uuid4().hex[:8]
            account_count = len(due_accounts)
            log_event(
                logger,
                logging.INFO,
                "usage_cycle_started",
                scheduler=USAGE_SYNC_LEASE_NAME,
                owner_id=lease.owner_id,
                run_id=run_id,
                account_count=account_count,
            )
            for index, account in enumerate(due_accounts):
                if not lease.is_valid():
                    cycle_reason = "lease_lost"
                    skipped_count += account_count - index
                    return
                current = db.get_opencode_account(account.id)
                if current is None or not current.enabled:
                    skipped_count += 1
                    continue
                account_started_at = time.monotonic()
                try:
                    result = await sync_usage_incremental(
                        current,
                        continuation_check=lease.is_valid,
                        lease_name=USAGE_SYNC_LEASE_NAME,
                        lease_owner_id=lease.owner_id,
                    )
                    if result.error:
                        skipped_count += 1
                        log_event(
                            logger,
                            logging.WARNING,
                            "usage_sync_result_discarded",
                            account_id=current.id,
                            provider="opencode",
                            run_id=run_id,
                            reason="source_deleted_disabled_or_changed",
                            pages_fetched=result.pages_fetched,
                            inserted=result.inserted,
                        )
                    else:
                        success_count += 1
                        log_event(
                            logger,
                            logging.INFO,
                            "usage_sync_completed",
                            account_id=current.id,
                            provider="opencode",
                            run_id=run_id,
                            pages_fetched=result.pages_fetched,
                            inserted=result.inserted,
                            duration_ms=round(
                                (time.monotonic() - account_started_at) * 1000
                            ),
                        )
                except UsageSyncInterrupted:
                    cycle_reason = "lease_lost"
                    skipped_count += account_count - index
                    return
                except Exception as exc:
                    failure_count += 1
                    log_event(
                        logger,
                        logging.WARNING,
                        "usage_sync_failed",
                        account_id=current.id,
                        provider="opencode",
                        run_id=run_id,
                        duration_ms=round((time.monotonic() - account_started_at) * 1000),
                        **safe_exception_fields(exc, "usage_sync_error"),
                    )
        except Exception as exc:
            cycle_reason = "unexpected_error"
            log_event(
                logger,
                logging.ERROR,
                "usage_cycle_failed",
                scheduler=USAGE_SYNC_LEASE_NAME,
                owner_id=lease.owner_id,
                **safe_exception_fields(exc, "unexpected_cycle_error"),
                **({"run_id": run_id} if run_id else {}),
            )
        finally:
            if run_id is not None:
                log_event(
                    logger,
                    logging.INFO if cycle_reason == "completed" else logging.WARNING,
                    "usage_cycle_completed",
                    scheduler=USAGE_SYNC_LEASE_NAME,
                    owner_id=lease.owner_id,
                    run_id=run_id,
                    account_count=account_count,
                    success_count=success_count,
                    failure_count=failure_count,
                    skipped_count=skipped_count,
                    duration_ms=round((time.monotonic() - cycle_started_at) * 1000),
                    reason=cycle_reason,
                )
            await lease.release()


async def _usage_auto_sync_loop() -> None:
    log_event(
        logger,
        logging.INFO,
        "scheduler_started",
        scheduler=USAGE_SYNC_LEASE_NAME,
        interval_sec=load_service_config().usage_sync.interval_sec,
    )
    while True:
        try:
            await _sync_due_usage_accounts()
            settings = load_service_config().usage_sync
            await asyncio.sleep(min(30, settings.interval_sec))
        except asyncio.CancelledError:
            log_event(
                logger,
                logging.INFO,
                "scheduler_stopped",
                scheduler=USAGE_SYNC_LEASE_NAME,
                reason="cancelled",
            )
            raise
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "scheduler_loop_recovered",
                scheduler=USAGE_SYNC_LEASE_NAME,
                **safe_exception_fields(exc, "unexpected_loop_error"),
            )
            await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _sync_task, _quota_task
    configure_logging()
    ensure_bootstrapped()
    service = load_service_config()
    log_event(logger, logging.INFO, "application_started", version=APP_VERSION)
    if service.usage_sync.auto_sync:
        _sync_task = asyncio.create_task(_usage_auto_sync_loop())
    _quota_task = asyncio.create_task(quota_sync_loop())
    try:
        yield
    finally:
        for task in (_sync_task, _quota_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        log_event(logger, logging.INFO, "application_stopped", version=APP_VERSION)


app = FastAPI(title="QuotaHub", version=APP_VERSION, lifespan=lifespan)

accounts_router = APIRouter(
    prefix="/api/admin/accounts",
    tags=["admin-accounts"],
    dependencies=[Depends(require_admin)],
)
auth_router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
cpa_router = APIRouter(
    prefix="/api/admin/cpa",
    tags=["admin-cpa"],
    dependencies=[Depends(require_admin)],
)


def _opencode_account_dict(row: db.OpenCodeAccountRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "workspace_id": row.workspace_id,
        "resolved_workspace_id": row.resolved_workspace_id,
        "auth_cookie_masked": mask_cookie(row.auth_cookie),
        "configured": bool(row.auth_cookie.strip()),
        "show_rolling": row.show_rolling,
        "show_weekly": row.show_weekly,
        "show_monthly": row.show_monthly,
        "enabled": row.enabled,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _ollama_account_dict(row: db.OllamaAccountRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "session_cookie_masked": mask_ollama_cookie(row.session_cookie),
        "configured": bool(row.session_cookie.strip()),
        "show_session": row.show_session,
        "show_weekly": row.show_weekly,
        "enabled": row.enabled,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _admin_cpa_channel_dict(channel_id: str) -> dict[str, Any]:
    channel = next(
        (
            item
            for item in db.list_cached_cpa_channels(enabled_only=False)
            if item.get("id") == channel_id
        ),
        None,
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="CPA 渠道不存在")
    return channel


def _safe_changed_fields(fields: dict[str, Any], secret_fields: set[str]) -> list[str]:
    changed = [key for key in fields if key not in secret_fields]
    if any(key in fields for key in secret_fields):
        changed.append("credentials")
    return sorted(changed)


def _build_config_response() -> dict[str, Any]:
    service = load_service_config()
    return {
        "refresh": {
            "ollama": {
                "auto_refresh": service.refresh_ollama.auto_refresh,
                "interval_sec": service.refresh_ollama.interval_sec,
            },
            "opencode_go": {
                "auto_refresh": service.refresh_opencode_go.auto_refresh,
                "interval_sec": service.refresh_opencode_go.interval_sec,
            },
        },
        "usage_sync": {
            "auto_sync": service.usage_sync.auto_sync,
            "interval_sec": service.usage_sync.interval_sec,
            "backfill_pages_per_request": service.usage_sync.backfill_pages_per_request,
            "max_pages_per_incremental": service.usage_sync.max_pages_per_incremental,
        },
        "quota_sync": {
            "ollama": {
                "auto_sync": service.quota_sync_ollama.auto_sync,
                "interval_sec": service.quota_sync_ollama.interval_sec,
            },
            "opencode_go": {
                "auto_sync": service.quota_sync_opencode_go.auto_sync,
                "interval_sec": service.quota_sync_opencode_go.interval_sec,
            },
        },
        "accounts_imported": db.imported_flag_path().exists()
        or db.count_opencode_accounts() > 0
        or db.count_ollama_accounts() > 0,
        "opencode_accounts": [_opencode_account_dict(row) for row in db.list_opencode_accounts()],
        "ollama_accounts": [_ollama_account_dict(row) for row in db.list_ollama_accounts()],
    }


@accounts_router.get("/opencode")
async def list_opencode_accounts() -> list[dict[str, Any]]:
    return [_opencode_account_dict(row) for row in db.list_opencode_accounts()]


@accounts_router.post("/opencode", dependencies=[Depends(require_csrf)])
async def create_opencode_account(body: OpenCodeAccountCreate) -> dict[str, Any]:
    if not body.auth_cookie.strip():
        raise HTTPException(status_code=400, detail="auth_cookie 不能为空")
    row = db.create_opencode_account(
        name=body.name.strip() or "OpenCode",
        workspace_id=body.workspace_id.strip() or "Default",
        auth_cookie=body.auth_cookie.strip(),
        show_rolling=body.show_rolling,
        show_weekly=body.show_weekly,
        show_monthly=body.show_monthly,
        enabled=body.enabled,
    )
    if row.enabled:
        wake_quota_sync()
    log_event(
        logger,
        logging.INFO,
        "admin_account_created",
        provider="opencode",
        account_id=row.id,
        enabled=row.enabled,
        credential_changed=True,
    )
    return _opencode_account_dict(row)


@accounts_router.get("/opencode/{account_id}")
async def get_opencode_account(account_id: str) -> dict[str, Any]:
    row = db.get_opencode_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return _opencode_account_dict(row)


@accounts_router.put("/opencode/{account_id}", dependencies=[Depends(require_csrf)])
async def update_opencode_account(account_id: str, body: OpenCodeAccountUpdate) -> dict[str, Any]:
    previous = db.get_opencode_account(account_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        fields["name"] = fields["name"].strip() or "OpenCode"
    if "workspace_id" in fields and fields["workspace_id"] is not None:
        fields["workspace_id"] = fields["workspace_id"].strip() or "Default"
        if fields["workspace_id"] != previous.workspace_id:
            fields["resolved_workspace_id"] = None
    if "auth_cookie" in fields and fields["auth_cookie"] is not None:
        fields["auth_cookie"] = fields["auth_cookie"].strip()
    for key in list(fields):
        if key != "resolved_workspace_id" and getattr(previous, key) == fields[key]:
            fields.pop(key)
    row = db.update_opencode_account(account_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    credential_changed = (
        row.auth_cookie != previous.auth_cookie
        or row.workspace_id != previous.workspace_id
    )
    reenabled = not previous.enabled and row.enabled
    if row.enabled and (credential_changed or reenabled):
        db.mark_quota_snapshot_due("opencode", account_id)
        wake_quota_sync()
    if fields:
        log_event(
            logger,
            logging.INFO,
            "admin_account_updated",
            provider="opencode",
            account_id=row.id,
            enabled=row.enabled,
            credential_changed=credential_changed,
            changed_fields=_safe_changed_fields(fields, {"auth_cookie"}),
        )
    return _opencode_account_dict(row)


@accounts_router.delete("/opencode/{account_id}", dependencies=[Depends(require_csrf)])
async def delete_opencode_account(account_id: str) -> dict[str, bool]:
    if not db.delete_opencode_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")
    log_event(
        logger,
        logging.INFO,
        "admin_account_deleted",
        provider="opencode",
        account_id=account_id,
    )
    return {"ok": True}


@accounts_router.post("/opencode/{account_id}/test", dependencies=[Depends(require_csrf)])
async def test_opencode_account(account_id: str) -> dict[str, Any]:
    row = db.get_opencode_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    try:
        workspace_id = await resolve_account_workspace_id(
            row.workspace_id,
            row.auth_cookie,
            row.resolved_workspace_id,
        )
        db.record_opencode_resolved_workspace(
            account_id,
            workspace_id,
            expected_collection_revision=row.collection_revision,
        )
        log_event(
            logger,
            logging.INFO,
            "admin_account_test_completed",
            provider="opencode",
            account_id=account_id,
            success_count=1,
        )
        return {"success": True, "workspace_id": workspace_id}
    except db.CollectionGuardRejected as exc:
        log_event(
            logger,
            logging.WARNING,
            "admin_account_test_failed",
            provider="opencode",
            account_id=account_id,
            **safe_exception_fields(exc, "source_changed"),
        )
        return {"success": False, "error": "账号配置已变化，请重试"}
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "admin_account_test_failed",
            provider="opencode",
            account_id=account_id,
            **safe_exception_fields(exc, "account_test_error"),
        )
        return {"success": False, "error": "账号连接测试失败"}


@accounts_router.get("/opencode/{account_id}/quota")
async def opencode_account_quota(account_id: str) -> dict[str, Any]:
    row = db.get_opencode_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    cached = db.get_cached_opencode_quota(account_id)
    return cached or {
        "account_id": account_id,
        "name": row.name,
        "success": False,
        "updated_at": "",
        "error": "等待首次采集",
        "windows": [],
    }


@accounts_router.get("/opencode/{account_id}/usage")
async def list_account_usage(
    account_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    key_id: str | None = None,
) -> dict[str, Any]:
    if db.get_opencode_account(account_id) is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    records, total = db.list_usage_records(account_id, offset=offset, limit=limit, key_id=key_id)
    sync = db.get_usage_sync_state(account_id)
    return {
        "records": [r.to_dict() for r in records],
        "total": total,
        "offset": offset,
        "limit": limit,
        "key_ids": db.list_usage_key_ids(account_id),
        "sync": sync.to_dict(),
    }


@accounts_router.get("/opencode/{account_id}/usage/status")
async def usage_sync_status(account_id: str) -> dict[str, Any]:
    if db.get_opencode_account(account_id) is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    return db.get_usage_sync_state(account_id).to_dict()


@accounts_router.post(
    "/opencode/{account_id}/usage/sync", dependencies=[Depends(require_csrf)]
)
async def usage_sync(account_id: str) -> dict[str, Any]:
    row = db.get_opencode_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if _usage_sync_lock.locked():
        raise HTTPException(status_code=409, detail="使用记录同步正在进行")
    async with _usage_sync_lock:
        lease = SchedulerLease(USAGE_SYNC_LEASE_NAME, owner_id=str(uuid.uuid4()))
        if not await lease.acquire():
            raise HTTPException(status_code=409, detail="使用记录同步正在进行")
        try:
            result = await sync_usage_incremental(
                row,
                continuation_check=lease.is_valid,
                lease_name=USAGE_SYNC_LEASE_NAME,
                lease_owner_id=lease.owner_id,
            )
            log_event(
                logger,
                logging.INFO if not result.error else logging.WARNING,
                "admin_usage_sync_completed",
                provider="opencode",
                account_id=account_id,
                pages_fetched=result.pages_fetched,
                inserted=result.inserted,
                reason="completed" if not result.error else "source_changed",
            )
            return result.to_dict()
        except UsageSyncInterrupted as exc:
            log_event(
                logger,
                logging.WARNING,
                "admin_usage_sync_failed",
                provider="opencode",
                account_id=account_id,
                **safe_exception_fields(exc, "lease_lost"),
            )
            raise HTTPException(status_code=409, detail="使用记录同步租约已失效") from exc
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "admin_usage_sync_failed",
                provider="opencode",
                account_id=account_id,
                **safe_exception_fields(exc, "usage_sync_error"),
            )
            raise HTTPException(status_code=502, detail="使用记录同步失败") from exc
        finally:
            await lease.release()


@accounts_router.post(
    "/opencode/{account_id}/usage/backfill", dependencies=[Depends(require_csrf)]
)
async def usage_backfill(
    account_id: str,
    pages: int = Query(5, ge=1, le=50),
) -> dict[str, Any]:
    row = db.get_opencode_account(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if _usage_sync_lock.locked():
        raise HTTPException(status_code=409, detail="使用记录同步正在进行")
    async with _usage_sync_lock:
        lease = SchedulerLease(USAGE_SYNC_LEASE_NAME, owner_id=str(uuid.uuid4()))
        if not await lease.acquire():
            raise HTTPException(status_code=409, detail="使用记录同步正在进行")
        try:
            result = await backfill_usage(
                row,
                max_pages=pages,
                continuation_check=lease.is_valid,
                lease_name=USAGE_SYNC_LEASE_NAME,
                lease_owner_id=lease.owner_id,
            )
            log_event(
                logger,
                logging.INFO if not result.error else logging.WARNING,
                "admin_usage_backfill_completed",
                provider="opencode",
                account_id=account_id,
                pages_fetched=result.pages_fetched,
                inserted=result.inserted,
                reason="completed" if not result.error else "source_changed",
            )
            return result.to_dict()
        except UsageSyncInterrupted as exc:
            log_event(
                logger,
                logging.WARNING,
                "admin_usage_backfill_failed",
                provider="opencode",
                account_id=account_id,
                **safe_exception_fields(exc, "lease_lost"),
            )
            raise HTTPException(status_code=409, detail="使用记录同步租约已失效") from exc
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "admin_usage_backfill_failed",
                provider="opencode",
                account_id=account_id,
                **safe_exception_fields(exc, "usage_backfill_error"),
            )
            raise HTTPException(status_code=502, detail="使用记录回填失败") from exc
        finally:
            await lease.release()


@accounts_router.get("/ollama")
async def list_ollama_accounts() -> list[dict[str, Any]]:
    return [_ollama_account_dict(row) for row in db.list_ollama_accounts()]


@accounts_router.post("/ollama", dependencies=[Depends(require_csrf)])
async def create_ollama_account(body: OllamaAccountCreate) -> dict[str, Any]:
    if not body.session_cookie.strip():
        raise HTTPException(status_code=400, detail="session_cookie 不能为空")
    row = db.create_ollama_account(
        name=body.name.strip() or "Ollama",
        session_cookie=body.session_cookie.strip(),
        show_session=body.show_session,
        show_weekly=body.show_weekly,
        enabled=body.enabled,
    )
    if row.enabled:
        wake_quota_sync()
    log_event(
        logger,
        logging.INFO,
        "admin_account_created",
        provider="ollama",
        account_id=row.id,
        enabled=row.enabled,
        credential_changed=True,
    )
    return _ollama_account_dict(row)


@accounts_router.put("/ollama/{account_id}", dependencies=[Depends(require_csrf)])
async def update_ollama_account(account_id: str, body: OllamaAccountUpdate) -> dict[str, Any]:
    previous = db.get_ollama_account(account_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        fields["name"] = fields["name"].strip() or "Ollama"
    if "session_cookie" in fields and fields["session_cookie"] is not None:
        fields["session_cookie"] = fields["session_cookie"].strip()
    for key in list(fields):
        if getattr(previous, key) == fields[key]:
            fields.pop(key)
    row = db.update_ollama_account(account_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    credential_changed = row.session_cookie != previous.session_cookie
    reenabled = not previous.enabled and row.enabled
    if row.enabled and (credential_changed or reenabled):
        db.mark_quota_snapshot_due("ollama", account_id)
        wake_quota_sync()
    if fields:
        log_event(
            logger,
            logging.INFO,
            "admin_account_updated",
            provider="ollama",
            account_id=row.id,
            enabled=row.enabled,
            credential_changed=credential_changed,
            changed_fields=_safe_changed_fields(fields, {"session_cookie"}),
        )
    return _ollama_account_dict(row)


@accounts_router.delete("/ollama/{account_id}", dependencies=[Depends(require_csrf)])
async def delete_ollama_account(account_id: str) -> dict[str, bool]:
    if not db.delete_ollama_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")
    log_event(
        logger,
        logging.INFO,
        "admin_account_deleted",
        provider="ollama",
        account_id=account_id,
    )
    return {"ok": True}


@auth_router.post("/login")
async def admin_login(body: AdminLogin, request: Request, response: Response) -> dict[str, Any]:
    ensure_bootstrapped()
    token_valid = verify_admin_token(body.token)
    decision = apply_login_attempt(request, success=token_valid)
    if not decision.allowed:
        log_event(
            logger,
            logging.WARNING,
            "admin_login_rate_limited",
            source_hmac=decision.source_hmac,
            failure_count=decision.failure_count,
        )
        raise HTTPException(status_code=429, detail="登录尝试过多，请稍后再试")
    if not token_valid:
        log_event(
            logger,
            logging.WARNING,
            "admin_login_failed",
            source_hmac=decision.source_hmac,
            failure_count=decision.failure_count,
        )
        raise HTTPException(status_code=401, detail="管理令牌无效")
    csrf_token = create_session(response)
    log_event(
        logger,
        logging.INFO,
        "admin_login_succeeded",
        source_hmac=decision.source_hmac,
        failure_count=0,
    )
    return {"authenticated": True, "csrf_token": csrf_token}


@auth_router.get("/session")
async def admin_session(_session_hash: str = Depends(require_admin)) -> dict[str, bool]:
    return {"authenticated": True}


@auth_router.post("/logout")
async def admin_logout(
    request: Request,
    response: Response,
    session_hash: str = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> dict[str, bool]:
    delete_session(session_hash)
    clear_session_cookies(response)
    log_event(
        logger,
        logging.INFO,
        "admin_logout",
        source_hmac=client_fingerprint(request),
    )
    return {"ok": True}


@cpa_router.get("/channels")
async def list_cpa_channels() -> list[dict[str, Any]]:
    return db.list_cached_cpa_channels(enabled_only=False)


@cpa_router.post("/channels", dependencies=[Depends(require_csrf)])
async def create_cpa_channel(body: CPAChannelCreate) -> dict[str, Any]:
    management_key = body.management_key.strip()
    if not management_key:
        raise HTTPException(status_code=400, detail="管理密钥不能为空")
    try:
        base_url = normalize_cpa_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="CPA URL 无效") from exc
    row = db.create_cpa_channel(
        name=body.name.strip() or "CPA",
        base_url=base_url,
        management_key=management_key,
        enabled=body.enabled,
        interval_sec=body.interval_sec,
    )
    if row.enabled:
        wake_quota_sync()
    log_event(
        logger,
        logging.INFO,
        "admin_cpa_channel_created",
        provider="cpa",
        channel_id=row.id,
        enabled=row.enabled,
        credential_changed=True,
    )
    return _admin_cpa_channel_dict(row.id)


@cpa_router.get("/channels/{channel_id}")
async def get_cpa_channel(channel_id: str) -> dict[str, Any]:
    return _admin_cpa_channel_dict(channel_id)


@cpa_router.put("/channels/{channel_id}", dependencies=[Depends(require_csrf)])
async def update_cpa_channel(
    channel_id: str, body: CPAChannelUpdate
) -> dict[str, Any]:
    previous = db.get_cpa_channel(channel_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="CPA 渠道不存在")
    fields = body.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        fields["name"] = fields["name"].strip() or "CPA"
    if "url" in fields:
        raw_url = fields.pop("url")
        if raw_url is not None:
            try:
                fields["base_url"] = normalize_cpa_url(raw_url)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="CPA URL 无效") from exc
    if "management_key" in fields and fields["management_key"] is not None:
        management_key = fields["management_key"].strip()
        if management_key:
            fields["management_key"] = management_key
        else:
            fields.pop("management_key")
    for key in list(fields):
        if getattr(previous, key) == fields[key]:
            fields.pop(key)
    row = db.update_cpa_channel(channel_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail="CPA 渠道不存在")
    credential_changed = (
        row.base_url != previous.base_url
        or row.management_key != previous.management_key
    )
    reenabled = not previous.enabled and row.enabled
    interval_changed = row.interval_sec != previous.interval_sec
    if row.enabled and (credential_changed or reenabled):
        db.mark_cpa_channel_due(channel_id)
        wake_quota_sync()
    elif row.enabled and interval_changed:
        wake_quota_sync()
    if fields:
        log_event(
            logger,
            logging.INFO,
            "admin_cpa_channel_updated",
            provider="cpa",
            channel_id=row.id,
            enabled=row.enabled,
            credential_changed=credential_changed,
            changed_fields=_safe_changed_fields(fields, {"management_key"}),
        )
    return _admin_cpa_channel_dict(row.id)


@cpa_router.delete("/channels/{channel_id}", dependencies=[Depends(require_csrf)])
async def delete_cpa_channel(channel_id: str) -> dict[str, bool]:
    if not db.delete_cpa_channel(channel_id):
        raise HTTPException(status_code=404, detail="CPA 渠道不存在")
    log_event(
        logger,
        logging.INFO,
        "admin_cpa_channel_deleted",
        provider="cpa",
        channel_id=channel_id,
    )
    return {"ok": True}


app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(cpa_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/quota", deprecated=True)
async def quota() -> list[dict]:
    return db.list_cached_opencode_quotas()


@app.get("/api/ollama/quota", deprecated=True)
async def ollama_quota() -> list[dict]:
    return db.list_cached_ollama_quotas()


@app.get("/api/public/quota")
async def public_quota() -> dict[str, Any]:
    return {
        "opencode": db.list_cached_opencode_quotas(),
        "ollama": db.list_cached_ollama_quotas(),
        "cpa_channels": db.list_cached_cpa_channels(),
    }


@app.get("/api/analytics/overview", deprecated=True)
async def analytics_overview() -> dict[str, Any]:
    try:
        return await build_overview()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="概览数据生成失败") from exc


@app.get("/api/public/overview")
async def public_overview() -> dict[str, Any]:
    return await build_overview()


@app.get("/api/analytics/opencode/daily", deprecated=True)
async def analytics_opencode_daily(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    return {"days": days, "stats": db.opencode_daily_stats(days)}


@app.get("/api/public/analytics/opencode/daily")
async def public_analytics_opencode_daily(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    return {"days": days, "stats": db.opencode_daily_stats(days)}


@app.get("/api/analytics/opencode/daily/models", deprecated=True)
async def analytics_opencode_daily_models(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    return {"days": days, "stats": db.opencode_daily_model_stats(days)}


@app.get("/api/public/analytics/opencode/daily/models")
async def public_analytics_opencode_daily_models(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    return {"days": days, "stats": db.opencode_daily_model_stats(days)}


@app.get("/api/admin/usage/all", dependencies=[Depends(require_admin)])
async def list_all_usage(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    account_id: str | None = None,
) -> dict[str, Any]:
    records, total = db.list_all_usage_records(offset=offset, limit=limit, account_id=account_id)
    accounts = db.list_opencode_accounts()
    return {
        "records": [r.to_dict() for r in records],
        "total": total,
        "offset": offset,
        "limit": limit,
        "accounts": [{"id": row.id, "name": row.name} for row in accounts],
    }


@app.get("/api/admin/config", dependencies=[Depends(require_admin)])
async def config_status() -> dict:
    try:
        ensure_bootstrapped()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="配置加载失败") from exc
    return _build_config_response()


@app.put(
    "/api/admin/config",
    dependencies=[Depends(require_admin), Depends(require_csrf)],
)
async def update_config(body: ServiceConfigUpdate) -> dict:
    try:
        ensure_bootstrapped()
        before = _build_config_response()
        updates: dict[str, Any] = {}
        if body.refresh is not None:
            updates["refresh"] = {
                key: value.model_dump(exclude_unset=True)
                for key, value in body.refresh.items()
            }
        if body.quota_sync is not None:
            updates["quota_sync"] = {
                key: value.model_dump(exclude_unset=True)
                for key, value in body.quota_sync.items()
            }
        if body.usage_sync is not None:
            updates["usage_sync"] = body.usage_sync.model_dump(exclude_unset=True)
        if body.opencode is not None:
            updates["opencode"] = body.opencode.model_dump(exclude_unset=True)
        update_service_config(updates)
        after = _build_config_response()
        if before["usage_sync"] != after["usage_sync"]:
            await restart_usage_sync_task()
        if before["quota_sync"] != after["quota_sync"]:
            wake_quota_sync()
        changed_sections = sorted(
            section
            for section in ("refresh", "quota_sync", "usage_sync")
            if before.get(section) != after.get(section)
        )
        if changed_sections:
            log_event(
                logger,
                logging.INFO,
                "admin_settings_updated",
                changed_sections=changed_sections,
            )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="配置更新失败") from exc
    return after


if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        static_file = (FRONTEND_DIST / full_path).resolve()
        try:
            static_file.relative_to(FRONTEND_DIST.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404) from exc
        if static_file.is_file():
            return FileResponse(static_file)
        index = FRONTEND_DIST / "index.html"
        if not index.exists():
            raise HTTPException(status_code=404)
        return FileResponse(index)


def run() -> None:
    import uvicorn

    configure_logging()
    ensure_bootstrapped()
    cfg = load_service_config()
    log_event(logger, logging.INFO, "console_entrypoint_starting", version=APP_VERSION)
    uvicorn.run(
        "app.main:app",
        host=cfg.listen_host,
        port=cfg.listen_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
