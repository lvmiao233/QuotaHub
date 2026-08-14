from __future__ import annotations

import asyncio
import logging
import os
import uuid

from . import db
from .logging_config import get_logger, log_event, safe_exception_fields

LEASE_TTL_SECONDS = 120
LEASE_HEARTBEAT_SECONDS = 30
_owner_pid: int | None = None
_owner_id: str | None = None
logger = get_logger("scheduler")


def process_owner_id() -> str:
    global _owner_id, _owner_pid
    pid = os.getpid()
    if _owner_id is None or _owner_pid != pid:
        _owner_pid = pid
        _owner_id = str(uuid.uuid4())
    return _owner_id


class SchedulerLease:
    def __init__(self, name: str, *, owner_id: str | None = None) -> None:
        self.name = name
        self.owner_id = owner_id or process_owner_id()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._lost = asyncio.Event()

    async def acquire(self) -> bool:
        try:
            acquired = db.acquire_scheduler_lease(
                self.name, self.owner_id, ttl_sec=LEASE_TTL_SECONDS
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "scheduler_lease_acquire_failed",
                lease_name=self.name,
                owner_id=self.owner_id,
                **safe_exception_fields(exc, "database_error"),
            )
            return False
        if acquired:
            self._heartbeat_task = asyncio.create_task(self._heartbeat())
            log_event(
                logger,
                logging.DEBUG,
                "scheduler_lease_acquired",
                lease_name=self.name,
                owner_id=self.owner_id,
            )
        else:
            log_event(
                logger,
                logging.DEBUG,
                "scheduler_lease_skipped",
                lease_name=self.name,
                owner_id=self.owner_id,
                reason="held_by_other_owner",
            )
        return acquired

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(LEASE_HEARTBEAT_SECONDS)
            try:
                renewed = db.renew_scheduler_lease(
                    self.name, self.owner_id, ttl_sec=LEASE_TTL_SECONDS
                )
            except Exception as exc:
                renewed = False
                self._mark_lost("heartbeat_database_error", exc)
            if not renewed:
                self._mark_lost("heartbeat_rejected")
                return

    def is_valid(self) -> bool:
        if self._lost.is_set():
            return False
        try:
            valid = db.holds_scheduler_lease(self.name, self.owner_id)
        except Exception as exc:
            self._mark_lost("validity_database_error", exc)
            return False
        if not valid:
            self._mark_lost("lease_expired_or_replaced")
        return valid

    def _mark_lost(self, reason: str, exc: BaseException | None = None) -> None:
        if self._lost.is_set():
            return
        self._lost.set()
        fields = {
            "lease_name": self.name,
            "owner_id": self.owner_id,
            "reason": reason,
        }
        if exc is not None:
            fields.update(safe_exception_fields(exc, "database_error"))
        log_event(logger, logging.WARNING, "scheduler_lease_lost", **fields)

    async def release(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        try:
            released = db.release_scheduler_lease(self.name, self.owner_id)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "scheduler_lease_release_failed",
                lease_name=self.name,
                owner_id=self.owner_id,
                **safe_exception_fields(exc, "database_error"),
            )
            return
        log_event(
            logger,
            logging.DEBUG,
            "scheduler_lease_released",
            lease_name=self.name,
            owner_id=self.owner_id,
            reason="released" if released else "not_owner",
        )
