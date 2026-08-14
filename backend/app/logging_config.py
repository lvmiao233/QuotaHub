from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO

LOG_LEVEL_ENV = "QUOTAHUB_LOG_LEVEL"
LOGGER_NAME = "quotahub"

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}
_ALLOWED_EVENTS = {
    "admin_account_created",
    "admin_account_deleted",
    "admin_account_test_completed",
    "admin_account_test_failed",
    "admin_account_updated",
    "admin_cpa_channel_created",
    "admin_cpa_channel_deleted",
    "admin_cpa_channel_updated",
    "admin_login_failed",
    "admin_login_rate_limited",
    "admin_login_succeeded",
    "admin_logout",
    "admin_sessions_revoked",
    "admin_settings_updated",
    "admin_usage_backfill_completed",
    "admin_usage_backfill_failed",
    "admin_usage_sync_completed",
    "admin_usage_sync_failed",
    "application_started",
    "application_stopped",
    "console_entrypoint_starting",
    "cpa_channel_authentication_failed",
    "cpa_channel_collection_completed",
    "cpa_channel_collection_failed",
    "cpa_active_fallback_skipped",
    "cpa_discovery_completed",
    "cpa_passive_snapshots_failed",
    "cpa_passive_snapshots_loaded",
    "cpa_passive_snapshots_unsupported",
    "quota_cycle_completed",
    "quota_cycle_failed",
    "quota_cycle_idle",
    "quota_cycle_skipped",
    "quota_cycle_started",
    "quota_job_completed",
    "quota_job_failed",
    "quota_job_interrupted",
    "quota_job_unexpected_error",
    "quota_result_discarded",
    "scheduler_lease_acquire_failed",
    "scheduler_lease_acquired",
    "scheduler_lease_lost",
    "scheduler_lease_release_failed",
    "scheduler_lease_released",
    "scheduler_lease_skipped",
    "scheduler_loop_recovered",
    "scheduler_restarted",
    "scheduler_started",
    "scheduler_stopped",
    "usage_cycle_completed",
    "usage_cycle_failed",
    "usage_cycle_idle",
    "usage_cycle_skipped",
    "usage_cycle_started",
    "usage_sync_completed",
    "usage_sync_failed",
    "usage_sync_result_discarded",
}
_ALLOWED_FIELDS = {
    "account_count",
    "account_id",
    "accounts_discovered",
    "accounts_remaining",
    "changed_fields",
    "changed_sections",
    "channel_id",
    "credential_changed",
    "cpa_jobs",
    "duration_ms",
    "enabled",
    "error_code",
    "error_location",
    "error_type",
    "failure_count",
    "inserted",
    "interval_sec",
    "job_count",
    "lease_name",
    "ollama_jobs",
    "opencode_jobs",
    "owner_id",
    "pages_fetched",
    "pid",
    "poll_seconds",
    "provider",
    "public_id",
    "quota_source",
    "reason",
    "run_id",
    "scheduler",
    "sessions_revoked",
    "skipped_count",
    "source_hmac",
    "success_count",
    "snapshot_count",
    "version",
    "windows_count",
}
_MAX_FIELD_LENGTH = 256


class SafeEventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        source = f"{Path(record.pathname).name}:{record.lineno}"
        event = str(getattr(record, "event", "application_event"))
        fields = getattr(record, "event_fields", {})
        suffix = ""
        if isinstance(fields, dict) and fields:
            rendered = [f"{key}={_render_value(fields[key])}" for key in sorted(fields)]
            suffix = " " + " ".join(rendered)
        return f"[{timestamp}] [{record.levelname}] [{source}] {event}{suffix}"


def _render_value(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if len(encoded) > _MAX_FIELD_LENGTH:
        encoded = encoded[: _MAX_FIELD_LENGTH - 3] + "..."
    return encoded


def configured_log_level() -> int:
    name = os.environ.get(LOG_LEVEL_ENV, "INFO").strip().upper() or "INFO"
    try:
        return _LEVELS[name]
    except KeyError as exc:
        allowed = ", ".join(_LEVELS)
        raise ValueError(f"{LOG_LEVEL_ENV} must be one of: {allowed}") from exc


def configure_logging(*, stream: TextIO | None = None) -> logging.Logger:
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
    access_logger.disabled = True

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(configured_log_level())
    logger.propagate = False

    for handler in list(logger.handlers):
        if getattr(handler, "_quotahub_safe_handler", False):
            logger.removeHandler(handler)
            handler.close()

    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setLevel(logger.level)
    handler.setFormatter(SafeEventFormatter())
    handler._quotahub_safe_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    suffix = name.strip().replace(" ", "_")
    return logging.getLogger(f"{LOGGER_NAME}.{suffix}" if suffix else LOGGER_NAME)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    /,
    **fields: Any,
) -> None:
    if event not in _ALLOWED_EVENTS:
        raise ValueError("unsupported log event")
    unknown = set(fields) - _ALLOWED_FIELDS
    if unknown:
        raise ValueError("unsupported log field(s)")
    logger.log(
        level,
        event,
        extra={"event": event, "event_fields": fields},
        stacklevel=2,
    )


def safe_exception_fields(exc: BaseException, error_code: str) -> dict[str, str]:
    return {
        "error_code": error_code,
        "error_type": type(exc).__name__,
        "error_location": _exception_location(exc.__traceback__),
    }


def _exception_location(tb: TracebackType | None) -> str:
    if tb is None:
        return "unknown"
    frames = traceback.extract_tb(tb)
    if not frames:
        return "unknown"
    frame = frames[-1]
    return f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
