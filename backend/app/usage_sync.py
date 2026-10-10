from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from . import db
from .config import load_service_config
from .db import OpenCodeAccountRow
from .opencode_usage import (
    USAGE_PAGE_SIZE,
    fetch_request_logs_page,
    iso_to_since_ms,
    resolve_account_workspace_id,
)


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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _ensure_workspace(account: OpenCodeAccountRow) -> str:
    workspace_id = resolve_account_workspace_id(
        account.workspace_id,
        account.auth_cookie,
        account.resolved_workspace_id,
    )
    if workspace_id != account.resolved_workspace_id:
        db.update_opencode_account(account.id, resolved_workspace_id=workspace_id)
    return workspace_id


async def sync_usage_incremental(account: OpenCodeAccountRow) -> SyncResult:
    cfg = load_service_config().usage_sync
    sync_at = _now_iso()
    inserted_total = 0
    pages_fetched = 0

    try:
        workspace_id = _ensure_workspace(account)
        state = db.get_usage_sync_state(account.id)
        since_ms = iso_to_since_ms(state.newest_record_at)

        while pages_fetched < cfg.max_pages_per_incremental:
            page = await fetch_request_logs_page(
                workspace_id=workspace_id,
                auth_cookie=account.auth_cookie,
                since_ms=since_ms,
            )
            if not page.records:
                break
            pages_fetched += 1

            new_in_page = db.insert_usage_records_ignore(
                account.id,
                workspace_id,
                [r.to_db_dict() for r in page.records],
            )
            inserted_total += new_in_page

            if new_in_page == 0:
                break
            if len(page.records) < USAGE_PAGE_SIZE:
                break
            latest_ms = max(iso_to_since_ms(r.created_at) or 0 for r in page.records)
            if since_ms is not None and latest_ms <= since_ms:
                break
            since_ms = latest_ms

        db.refresh_usage_sync_totals(account.id)
        db.update_usage_sync_state(
            account.id,
            last_sync_at=sync_at,
            last_sync_status="ok",
            last_sync_error=None,
            last_inserted_count=inserted_total,
        )
        db.refresh_usage_sync_totals(account.id)
        return SyncResult(inserted=inserted_total, pages_fetched=pages_fetched, sync_at=sync_at)
    except Exception as exc:
        db.update_usage_sync_state(
            account.id,
            last_sync_at=sync_at,
            last_sync_status="error",
            last_sync_error=str(exc),
            last_inserted_count=0,
        )
        raise


async def backfill_usage(account: OpenCodeAccountRow, max_pages: int | None = None) -> SyncResult:
    cfg = load_service_config().usage_sync
    pages_limit = max_pages if max_pages is not None else cfg.backfill_pages_per_request
    pages_limit = max(1, min(pages_limit, 50))
    sync_at = _now_iso()
    inserted_total = 0
    pages_fetched = 0

    try:
        workspace_id = _ensure_workspace(account)
        state = db.get_usage_sync_state(account.id)
        cursor = state.logs_cursor

        for _ in range(pages_limit):
            page = await fetch_request_logs_page(
                workspace_id=workspace_id,
                auth_cookie=account.auth_cookie,
                cursor=cursor,
            )
            if not page.records:
                break
            pages_fetched += 1

            new_in_page = db.insert_usage_records_ignore(
                account.id,
                workspace_id,
                [r.to_db_dict() for r in page.records],
            )
            inserted_total += new_in_page
            cursor = page.next_cursor
            db.update_usage_sync_state(account.id, logs_cursor=cursor, deepest_page_fetched=pages_fetched)

            if not cursor:
                break
            if len(page.records) < USAGE_PAGE_SIZE:
                break

        db.refresh_usage_sync_totals(account.id)
        db.update_usage_sync_state(
            account.id,
            last_sync_at=sync_at,
            last_sync_status="ok",
            last_sync_error=None,
            last_inserted_count=inserted_total,
            logs_cursor=cursor,
        )
        return SyncResult(inserted=inserted_total, pages_fetched=pages_fetched, sync_at=sync_at)
    except Exception as exc:
        db.update_usage_sync_state(
            account.id,
            last_sync_at=sync_at,
            last_sync_status="error",
            last_sync_error=str(exc),
            last_inserted_count=0,
        )
        raise
