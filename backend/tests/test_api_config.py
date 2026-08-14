import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import db
from app.bootstrap import ensure_bootstrapped
from app.main import app


def _admin_client() -> TestClient:
    client = TestClient(app)
    login = client.post(
        "/api/admin/auth/login",
        json={"token": "test-admin-token-with-at-least-32-characters"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client


def test_update_config_persists_to_database(temp_data_dir):
    ensure_bootstrapped()
    client = _admin_client()

    resp = client.put(
        "/api/admin/config",
        json={
            "refresh": {
                "ollama": {"auto_refresh": False, "interval_sec": 120},
                "opencode_go": {"auto_refresh": True, "interval_sec": 90},
            },
            "usage_sync": {
                "auto_sync": False,
                "interval_sec": 600,
                "backfill_pages_per_request": 3,
                "max_pages_per_incremental": 8,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["refresh"]["ollama"]["auto_refresh"] is False
    assert data["refresh"]["ollama"]["interval_sec"] == 120
    assert data["refresh"]["opencode_go"]["interval_sec"] == 90
    assert data["usage_sync"]["auto_sync"] is False
    assert data["usage_sync"]["backfill_pages_per_request"] == 3

    stored = db.get_service_settings_payload()
    assert stored["refresh"]["ollama"]["auto_refresh"] is False
    assert stored["usage_sync"]["max_pages_per_incremental"] == 8

    get_resp = client.get("/api/admin/config")
    assert get_resp.json()["usage_sync"]["max_pages_per_incremental"] == 8


def test_migrate_settings_from_legacy_files(temp_data_dir, monkeypatch: pytest.MonkeyPatch):
    config = temp_data_dir / "config.json"
    monkeypatch.setenv("QUOTAHUB_CONFIG", str(config))
    config.write_text(
        json.dumps(
            {
                "refresh": {
                    "ollama": {"auto_refresh": False, "interval_sec": 111},
                },
                "usage_sync": {"interval_sec": 222},
            }
        ),
        encoding="utf-8",
    )
    service = temp_data_dir / "service.json"
    service.write_text(
        json.dumps(
            {
                "refresh": {
                    "opencode_go": {"interval_sec": 333},
                },
                "usage_sync": {"auto_sync": False},
            }
        ),
        encoding="utf-8",
    )

    ensure_bootstrapped()

    stored = db.get_service_settings_payload()
    assert stored["refresh"]["ollama"]["auto_refresh"] is False
    assert stored["refresh"]["ollama"]["interval_sec"] == 111
    assert stored["refresh"]["opencode_go"]["interval_sec"] == 333
    assert stored["usage_sync"]["interval_sec"] == 222
    assert stored["usage_sync"]["auto_sync"] is False

    client = _admin_client()
    resp = client.get("/api/admin/config")
    assert resp.status_code == 200
    assert resp.json()["refresh"]["ollama"]["interval_sec"] == 111


def test_config_updates_only_restart_changed_scheduler_partition(temp_data_dir):
    ensure_bootstrapped()
    client = _admin_client()
    restart = AsyncMock()
    save_settings = db.save_service_settings_payload
    with (
        patch("app.main.restart_usage_sync_task", restart),
        patch("app.main.wake_quota_sync") as wake,
        patch(
            "app.db.save_service_settings_payload", wraps=save_settings
        ) as save,
    ):
        assert client.put("/api/admin/config", json={}).status_code == 200
        save.assert_not_called()
        restart.assert_not_awaited()
        wake.assert_not_called()

        current = client.get("/api/admin/config").json()
        assert client.put(
            "/api/admin/config",
            json={"quota_sync": current["quota_sync"]},
        ).status_code == 200
        save.assert_not_called()
        restart.assert_not_awaited()
        wake.assert_not_called()

        assert client.put(
            "/api/admin/config",
            json={
                "quota_sync": {
                    "ollama": {
                        "interval_sec": current["quota_sync"]["ollama"]["interval_sec"]
                        + 300
                    }
                }
            },
        ).status_code == 200
        wake.assert_called_once()
        restart.assert_not_awaited()


def test_config_api_does_not_expose_unexpected_error_text(temp_data_dir):
    ensure_bootstrapped()
    client = _admin_client()
    sentinel = "config-exception-secret-sentinel"

    with patch("app.main.ensure_bootstrapped", side_effect=ValueError(sentinel)):
        response = client.get("/api/admin/config")

    assert response.status_code == 500
    assert response.json()["detail"] == "配置加载失败"
    assert sentinel not in response.text
