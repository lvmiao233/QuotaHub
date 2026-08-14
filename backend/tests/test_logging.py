from __future__ import annotations

import asyncio
import io
import logging
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import db
from app.logging_config import (
    configure_logging,
    get_logger,
    log_event,
    safe_exception_fields,
)
from app.main import app, run
from app.cpa_quota import CPAAuthAccount, CPAError
from app.quota_sync import collect_cpa_channel, quota_sync_loop
from app.scheduler import SchedulerLease


def test_safe_event_format_and_exception_message_redaction(monkeypatch):
    monkeypatch.setenv("QUOTAHUB_LOG_LEVEL", "DEBUG")
    stream = io.StringIO()
    configure_logging(stream=stream)
    logger = get_logger("test")
    assert logging.getLogger("uvicorn.access").disabled is True
    secret_message = "cookie-sentinel management-key-sentinel auth-index-sentinel"

    try:
        raise RuntimeError(secret_message)
    except RuntimeError as exc:
        log_event(
            logger,
            logging.ERROR,
            "quota_job_failed",
            provider="cpa",
            account_id="account-safe-id",
            **safe_exception_fields(exc, "controlled_error"),
        )

    output = stream.getvalue()
    assert re.search(
        r"^\[\d{4}-\d{2}-\d{2}T.*Z\] \[ERROR\] \[test_logging.py:\d+\] quota_job_failed ",
        output,
    )
    assert 'error_code="controlled_error"' in output
    assert 'error_type="RuntimeError"' in output
    assert "cookie-sentinel" not in output
    assert "management-key-sentinel" not in output
    assert "auth-index-sentinel" not in output

    with pytest.raises(ValueError, match="unsupported log field"):
        log_event(logger, logging.INFO, "application_started", auth_index="forbidden")

    with pytest.raises(ValueError, match="unsupported log event"):
        log_event(logger, logging.INFO, secret_message)
    assert secret_message not in stream.getvalue()


def test_invalid_log_level_is_rejected(monkeypatch):
    monkeypatch.setenv("QUOTAHUB_LOG_LEVEL", "TRACE")
    with pytest.raises(ValueError, match="QUOTAHUB_LOG_LEVEL"):
        configure_logging(stream=io.StringIO())


def test_login_log_uses_full_hmac_without_raw_source_or_token(temp_data_dir):
    stream = io.StringIO()
    configure_logging(stream=stream)
    client = TestClient(app)
    invalid_token = "invalid-admin-token-sentinel"

    response = client.post("/api/admin/auth/login", json={"token": invalid_token})

    assert response.status_code == 401
    output = stream.getvalue()
    match = re.search(r'source_hmac="(hmac:v1:[0-9a-f]{64})"', output)
    assert match is not None
    assert "testclient" not in output
    assert invalid_token not in output


@pytest.mark.asyncio
async def test_scheduler_loop_logs_and_recovers_without_exception_message(monkeypatch):
    monkeypatch.setenv("QUOTAHUB_LOG_LEVEL", "DEBUG")
    stream = io.StringIO()
    configure_logging(stream=stream)
    secret_message = "upstream-body-sentinel cookie-sentinel"
    collect = AsyncMock(
        side_effect=[RuntimeError(secret_message), asyncio.CancelledError()]
    )

    async def skip_wait(awaitable, *, timeout):
        awaitable.close()
        return None

    with (
        patch("app.quota_sync.collect_due_quotas", collect),
        patch("app.quota_sync.asyncio.wait_for", side_effect=skip_wait),
    ):
        with pytest.raises(asyncio.CancelledError):
            await quota_sync_loop()

    assert collect.await_count == 2
    output = stream.getvalue()
    assert "scheduler_loop_recovered" in output
    assert "scheduler_stopped" in output
    assert secret_message not in output
    assert "cookie-sentinel" not in output


@pytest.mark.asyncio
async def test_lease_heartbeat_failure_is_logged(monkeypatch):
    monkeypatch.setenv("QUOTAHUB_LOG_LEVEL", "DEBUG")
    stream = io.StringIO()
    configure_logging(stream=stream)
    lease = SchedulerLease("heartbeat-test", owner_id="owner-safe-id")

    with (
        patch("app.scheduler.asyncio.sleep", AsyncMock(return_value=None)),
        patch("app.scheduler.db.renew_scheduler_lease", return_value=False),
    ):
        await lease._heartbeat()

    assert lease.is_valid() is False
    output = stream.getvalue()
    assert "scheduler_lease_lost" in output
    assert 'lease_name="heartbeat-test"' in output
    assert 'reason="heartbeat_rejected"' in output


@pytest.mark.asyncio
async def test_cpa_collection_logs_never_include_channel_secrets(temp_data_dir):
    stream = io.StringIO()
    configure_logging(stream=stream)
    management_key = "management-key-sentinel"
    channel = db.create_cpa_channel(
        name="channel-name-sentinel",
        base_url="https://secret-url-sentinel.example.com",
        management_key=management_key,
    )
    upstream_secret = (
        "cookie-sentinel auth-index-sentinel person-sentinel@example.com "
        "upstream-body-sentinel"
    )

    with patch(
        "app.quota_sync.discover_cpa_accounts",
        AsyncMock(side_effect=RuntimeError(upstream_secret)),
    ):
        assert await collect_cpa_channel(channel, run_id="safe-run") is False

    output = stream.getvalue()
    for secret in (
        management_key,
        "channel-name-sentinel",
        "secret-url-sentinel",
        "cookie-sentinel",
        "auth-index-sentinel",
        "person-sentinel@example.com",
        "upstream-body-sentinel",
    ):
        assert secret not in output
    assert "cpa_channel_collection_failed" in output


@pytest.mark.asyncio
async def test_cpa_passive_and_active_fallback_logs_redact_snapshot_identity(
    temp_data_dir,
):
    stream = io.StringIO()
    configure_logging(stream=stream)
    channel = db.create_cpa_channel(
        name="channel-secret-sentinel",
        base_url="https://url-secret-sentinel.example.com",
        management_key="management-secret-sentinel",
    )
    account = CPAAuthAccount(
        auth_index="auth-index-secret-sentinel",
        auth_file_name="file-secret-sentinel.json",
        account_key_hash="internal-safe-hash",
        account_display="e***@example.com",
        plan="Plus",
    )
    with (
        patch(
            "app.quota_sync.discover_cpa_accounts",
            AsyncMock(return_value=[account]),
        ),
        patch(
            "app.quota_sync.fetch_cpa_header_snapshots",
            AsyncMock(
                return_value=[
                    {
                        "timestamp_ms": 1,
                        "auth_file_snapshot": account.auth_file_name,
                        "auth_index": account.auth_index,
                        "response_metadata": {
                            "quota": {"private-body-sentinel": True}
                        },
                    }
                ]
            ),
        ),
        patch(
            "app.quota_sync.fetch_cpa_account_quota",
            AsyncMock(side_effect=CPAError("exception-secret-sentinel")),
        ),
    ):
        assert await collect_cpa_channel(channel, run_id="safe-run") is True

    output = stream.getvalue()
    for secret in (
        "channel-secret-sentinel",
        "url-secret-sentinel",
        "management-secret-sentinel",
        "auth-index-secret-sentinel",
        "file-secret-sentinel",
        "e***@example.com",
        "private-body-sentinel",
        "exception-secret-sentinel",
    ):
        assert secret not in output
    assert "cpa_passive_snapshots_loaded" in output
    assert "quota_job_failed" in output


def test_console_entrypoint_bootstraps_an_empty_database(
    monkeypatch, tmp_path: Path
):
    data_dir = tmp_path / "empty-data"
    monkeypatch.setenv("QUOTAHUB_DATA", str(data_dir))
    monkeypatch.setenv("QUOTAHUB_CONFIG", str(tmp_path / "missing-config.json"))
    monkeypatch.setenv(
        "QUOTAHUB_ADMIN_TOKEN", "console-test-admin-token-with-32-characters"
    )
    monkeypatch.setenv("QUOTAHUB_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("QUOTAHUB_LOG_LEVEL", "INFO")

    with patch("uvicorn.run") as uvicorn_run:
        run()

    uvicorn_run.assert_called_once()
    assert uvicorn_run.call_args.kwargs["host"] == "127.0.0.1"
    assert uvicorn_run.call_args.kwargs["port"] == 8788
    with db.get_conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM service_settings"
        ).fetchone()[0] == 1
