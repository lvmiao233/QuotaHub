from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from . import db
from .config import load_service_config
from .db import OpenCodeAccountRow
from .opencode_usage import USAGE_PAGE_SIZE, fetch_usage_page, resolve_account_workspace_id


@dataclass
class SyncResult:
    inserted: int
    pages_fetched: int
    sync_at: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "inserted": self.inserted,
            "pages_fetched": self.pages_fetched,
            "sync_at": self.sync_at,
        }
        if self.error:
            payload["error"] = self.error
        return payload


class UsageSyncSuperseded(RuntimeError):
    pass


class UsageSyncInterrupted(RuntimeError):
    pass


ContinuationCheck = Callable[[], bool]


def _require_continuation(continuation_check: ContinuationCheck | None) -> None:
    if continuation_check is not None and not continuation_check():
        raise UsageSyncInterrupted("scheduler lease lost")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _require_current_account(account: OpenCodeAccountRow) -> OpenCodeAccountRow:
    current = db.get_opencode_account(account.id)
    if (
        current is None
        or not current.enabled
        or current.collection_revision != account.collection_revision
        or current.auth_cookie != account.auth_cookie
        or current.workspace_id != account.workspace_id
    ):
        raise UsageSyncSuperseded("账号配置已变化，已丢弃本次同步结果")
    return current


def _raise_guard_rejection(exc: db.CollectionGuardRejected) -> None:
    if exc.reason == "lease_lost":
        raise UsageSyncInterrupted("scheduler lease lost") from exc
    raise UsageSyncSuperseded("账号配置已变化，已丢弃本次同步结果") from exc


def _guard_rejection_result(
    exc: db.CollectionGuardRejected,
    *,
    inserted: int,
    pages_fetched: int,
    sync_at: str,
) -> SyncResult:
    if exc.reason == "lease_lost":
        raise UsageSyncInterrupted("scheduler lease lost") from exc
    return SyncResult(
        inserted=inserted,
        pages_fetched=pages_fetched,
        sync_at=sync_at,
        error="账号配置已变化，已丢弃本次同步结果",
    )


async def _ensure_workspace(
    account: OpenCodeAccountRow,
    continuation_check: ContinuationCheck | None = None,
    *,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> str:
    _require_continuation(continuation_check)
    workspace_id = await resolve_account_workspace_id(
        account.workspace_id,
        account.auth_cookie,
        account.resolved_workspace_id,
    )
    _require_continuation(continuation_check)
    current = _require_current_account(account)
    if workspace_id != current.resolved_workspace_id:
        _require_continuation(continuation_check)
        try:
            db.record_opencode_resolved_workspace(
                account.id,
                workspace_id,
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
            )
        except db.CollectionGuardRejected as exc:
            _raise_guard_rejection(exc)
    return workspace_id


async def sync_usage_incremental(
    account: OpenCodeAccountRow,
    *,
    continuation_check: ContinuationCheck | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> SyncResult:
    cfg = load_service_config().usage_sync
    sync_at = _now_iso()
    inserted_total = 0
    pages_fetched = 0

    try:
        _require_continuation(continuation_check)
        _require_current_account(account)
        workspace_id = await _ensure_workspace(
            account,
            continuation_check,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        page = 0
        while page < cfg.max_pages_per_incremental:
            _require_continuation(continuation_check)
            records = await fetch_usage_page(
                workspace_id=workspace_id,
                auth_cookie=account.auth_cookie,
                page=page,
            )
            _require_continuation(continuation_check)
            _require_current_account(account)
            if not records:
                break
            pages_fetched += 1

            _require_continuation(continuation_check)
            new_in_page = db.insert_usage_records_ignore(
                account.id,
                workspace_id,
                [r.to_db_dict() for r in records],
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
            )
            inserted_total += new_in_page

            if new_in_page == 0:
                break
            if new_in_page < len(records):
                break
            if len(records) < USAGE_PAGE_SIZE:
                break
            page += 1

        _require_continuation(continuation_check)
        _require_current_account(account)
        _require_continuation(continuation_check)
        db.refresh_usage_sync_totals(
            account.id,
            expected_collection_revision=account.collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        state = db.get_usage_sync_state(account.id)
        deepest = max(state.deepest_page_fetched, page) if pages_fetched else state.deepest_page_fetched
        _require_continuation(continuation_check)
        db.update_usage_sync_state(
            account.id,
            expected_collection_revision=account.collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
            last_sync_at=sync_at,
            last_sync_status="ok",
            last_sync_error=None,
            last_inserted_count=inserted_total,
            deepest_page_fetched=deepest,
        )
        db.refresh_usage_sync_totals(
            account.id,
            expected_collection_revision=account.collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        return SyncResult(inserted=inserted_total, pages_fetched=pages_fetched, sync_at=sync_at)
    except UsageSyncInterrupted:
        raise
    except db.CollectionGuardRejected as exc:
        return _guard_rejection_result(
            exc,
            inserted=inserted_total,
            pages_fetched=pages_fetched,
            sync_at=sync_at,
        )
    except UsageSyncSuperseded as exc:
        return SyncResult(
            inserted=inserted_total,
            pages_fetched=pages_fetched,
            sync_at=sync_at,
            error=str(exc),
        )
    except Exception as exc:
        _require_continuation(continuation_check)
        try:
            db.update_usage_sync_state(
                account.id,
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
                last_sync_at=sync_at,
                last_sync_status="error",
                last_sync_error="使用记录同步失败",
                last_inserted_count=0,
            )
        except db.CollectionGuardRejected as guard_exc:
            return _guard_rejection_result(
                guard_exc,
                inserted=inserted_total,
                pages_fetched=pages_fetched,
                sync_at=sync_at,
            )
        raise


async def backfill_usage(
    account: OpenCodeAccountRow,
    max_pages: int | None = None,
    *,
    continuation_check: ContinuationCheck | None = None,
    lease_name: str | None = None,
    lease_owner_id: str | None = None,
) -> SyncResult:
    cfg = load_service_config().usage_sync
    pages_limit = max_pages if max_pages is not None else cfg.backfill_pages_per_request
    pages_limit = max(1, min(pages_limit, 50))
    sync_at = _now_iso()
    inserted_total = 0
    pages_fetched = 0

    try:
        _require_continuation(continuation_check)
        _require_current_account(account)
        workspace_id = await _ensure_workspace(
            account,
            continuation_check,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        state = db.get_usage_sync_state(account.id)
        start_page = state.deepest_page_fetched + 1 if state.deepest_page_fetched >= 0 else 0
        page = start_page

        for _ in range(pages_limit):
            _require_continuation(continuation_check)
            records = await fetch_usage_page(
                workspace_id=workspace_id,
                auth_cookie=account.auth_cookie,
                page=page,
            )
            _require_continuation(continuation_check)
            _require_current_account(account)
            if not records:
                break
            pages_fetched += 1

            _require_continuation(continuation_check)
            new_in_page = db.insert_usage_records_ignore(
                account.id,
                workspace_id,
                [r.to_db_dict() for r in records],
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
            )
            inserted_total += new_in_page
            _require_continuation(continuation_check)
            db.update_usage_sync_state(
                account.id,
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
                deepest_page_fetched=page,
            )

            if len(records) < USAGE_PAGE_SIZE:
                break
            page += 1

        _require_continuation(continuation_check)
        _require_current_account(account)
        _require_continuation(continuation_check)
        db.refresh_usage_sync_totals(
            account.id,
            expected_collection_revision=account.collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
        )
        _require_continuation(continuation_check)
        db.update_usage_sync_state(
            account.id,
            expected_collection_revision=account.collection_revision,
            lease_name=lease_name,
            lease_owner_id=lease_owner_id,
            last_sync_at=sync_at,
            last_sync_status="ok",
            last_sync_error=None,
            last_inserted_count=inserted_total,
        )
        return SyncResult(inserted=inserted_total, pages_fetched=pages_fetched, sync_at=sync_at)
    except UsageSyncInterrupted:
        raise
    except db.CollectionGuardRejected as exc:
        return _guard_rejection_result(
            exc,
            inserted=inserted_total,
            pages_fetched=pages_fetched,
            sync_at=sync_at,
        )
    except UsageSyncSuperseded as exc:
        return SyncResult(
            inserted=inserted_total,
            pages_fetched=pages_fetched,
            sync_at=sync_at,
            error=str(exc),
        )
    except Exception as exc:
        _require_continuation(continuation_check)
        try:
            db.update_usage_sync_state(
                account.id,
                expected_collection_revision=account.collection_revision,
                lease_name=lease_name,
                lease_owner_id=lease_owner_id,
                last_sync_at=sync_at,
                last_sync_status="error",
                last_sync_error="使用记录回填失败",
                last_inserted_count=0,
            )
        except db.CollectionGuardRejected as guard_exc:
            return _guard_rejection_result(
                guard_exc,
                inserted=inserted_total,
                pages_fetched=pages_fetched,
                sync_at=sync_at,
            )
        raise
