from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.quota import LABEL_MONTHLY, LABEL_ROLLING, LABEL_WEEKLY


def _admin_client() -> TestClient:
    client = TestClient(app)
    login = client.post(
        "/api/admin/auth/login",
        json={"token": "test-admin-token-with-at-least-32-characters"},
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client


def test_opencode_account_quota_returns_dict(temp_data_dir):
    client = _admin_client()
    row = db.create_opencode_account(
        name="Test",
        workspace_id="Default",
        auth_cookie="auth=testcookie",
    )
    db.record_opencode_quota_snapshot(
        row.id,
        success=True,
        attempted_at="2026-01-01T00:00:00Z",
        windows=[
            {
                "label": LABEL_ROLLING,
                "used": 10.0,
                "remaining": 90.0,
                "total": 100.0,
                "unit": "%",
                "reset_at": "2026-01-01T05:00:00Z",
                "reset_in_sec": 3600,
            },
            {
                "label": LABEL_WEEKLY,
                "used": 20.0,
                "remaining": 80.0,
                "total": 100.0,
                "unit": "%",
                "reset_at": "2026-01-08T00:00:00Z",
                "reset_in_sec": 86400,
            },
            {
                "label": LABEL_MONTHLY,
                "used": 30.0,
                "remaining": 70.0,
                "total": 100.0,
                "unit": "%",
                "reset_at": "2026-02-01T00:00:00Z",
                "reset_in_sec": 2592000,
            },
        ],
    )
    resp = client.get(f"/api/admin/accounts/opencode/{row.id}/quota")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert data["success"] is True
    assert data["name"] == "Test"
    assert len(data["windows"]) == 3
    assert data["windows"][0]["label"] == LABEL_ROLLING


def test_opencode_display_update_does_not_force_quota_collection(temp_data_dir):
    client = _admin_client()
    row = db.create_opencode_account(
        name="Before", workspace_id="Default", auth_cookie="auth=secret"
    )
    db.record_opencode_quota_snapshot(
        row.id, success=True, attempted_at="2026-08-11T08:00:00Z", windows=[]
    )

    with patch("app.main.wake_quota_sync") as wake:
        response = client.put(
            f"/api/admin/accounts/opencode/{row.id}",
            json={"name": "After", "show_weekly": False},
        )
    assert response.status_code == 200
    assert db.get_quota_snapshot_attempt("opencode", row.id) == "2026-08-11T08:00:00Z"
    wake.assert_not_called()

    with patch("app.main.wake_quota_sync") as wake:
        response = client.put(
            f"/api/admin/accounts/opencode/{row.id}",
            json={"auth_cookie": "auth=changed"},
        )
    assert response.status_code == 200
    assert db.get_quota_snapshot_attempt("opencode", row.id) is None
    wake.assert_called_once()


def test_opencode_cookie_update_invalidates_resolved_workspace(temp_data_dir):
    client = _admin_client()
    row = db.create_opencode_account(
        name="Workspace", workspace_id="Default", auth_cookie="auth=old"
    )
    db.record_opencode_resolved_workspace(
        row.id,
        "wrk_cached",
        expected_collection_revision=row.collection_revision,
    )

    response = client.put(
        f"/api/admin/accounts/opencode/{row.id}",
        json={"auth_cookie": "auth=new"},
    )

    assert response.status_code == 200
    assert response.json()["resolved_workspace_id"] is None
    current = db.get_opencode_account(row.id)
    assert current.resolved_workspace_id is None
    assert current.collection_revision == row.collection_revision + 1


def test_admin_account_and_usage_errors_do_not_expose_exception_text(temp_data_dir):
    client = _admin_client()
    row = db.create_opencode_account(
        name="Safe Errors", workspace_id="Default", auth_cookie="auth=safe"
    )
    sentinel = "api-exception-secret-sentinel"

    with patch(
        "app.main.resolve_account_workspace_id",
        AsyncMock(side_effect=RuntimeError(sentinel)),
    ):
        test_response = client.post(
            f"/api/admin/accounts/opencode/{row.id}/test"
        )
    assert test_response.status_code == 200
    assert test_response.json() == {
        "success": False,
        "error": "账号连接测试失败",
    }
    assert sentinel not in test_response.text

    with patch(
        "app.main.sync_usage_incremental",
        AsyncMock(side_effect=RuntimeError(sentinel)),
    ):
        sync_response = client.post(
            f"/api/admin/accounts/opencode/{row.id}/usage/sync"
        )
    assert sync_response.status_code == 502
    assert sync_response.json()["detail"] == "使用记录同步失败"
    assert sentinel not in sync_response.text
