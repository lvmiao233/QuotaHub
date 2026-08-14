from __future__ import annotations

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.secrets import ENCRYPTED_PREFIX


ADMIN_TOKEN = "test-admin-token-with-at-least-32-characters"


def _admin_client() -> TestClient:
    client = TestClient(app)
    login = client.post("/api/admin/auth/login", json={"token": ADMIN_TOKEN})
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client


def test_cpa_channel_crud_encrypts_key_and_never_returns_it(temp_data_dir):
    client = _admin_client()
    created = client.post(
        "/api/admin/cpa/channels",
        json={
            "name": "Primary CPA",
            "url": "https://proxy.example.com/",
            "management_key": "management-key-should-stay-server-side",
            "interval_sec": 600,
        },
    )
    assert created.status_code == 200
    payload = created.json()
    channel_id = payload["id"]
    assert payload["url"] == "https://proxy.example.com"
    assert payload["enabled"] is True
    assert payload["interval_sec"] == 600
    assert "management_key" not in payload
    assert "configured" not in payload

    with db.get_conn() as conn:
        stored = conn.execute(
            "SELECT management_key FROM cpa_channels WHERE id = ?", (channel_id,)
        ).fetchone()[0]
    assert stored.startswith(ENCRYPTED_PREFIX)
    assert "management-key-should-stay-server-side" not in stored

    updated = client.put(
        f"/api/admin/cpa/channels/{channel_id}",
        json={"management_key": "", "enabled": False, "interval_sec": 900},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert db.get_cpa_channel(channel_id).management_key == "management-key-should-stay-server-side"

    anonymous = TestClient(app)
    assert anonymous.get("/api/admin/cpa/channels").status_code == 401
    assert anonymous.post(
        "/api/admin/cpa/channels",
        json={"name": "x", "url": "https://x.example", "management_key": "x"},
    ).status_code == 401

    deleted = client.delete(f"/api/admin/cpa/channels/{channel_id}")
    assert deleted.status_code == 200
    assert db.get_cpa_channel(channel_id) is None


def test_cpa_disabled_channel_hidden_publicly_and_delete_cascades_snapshots(temp_data_dir):
    channel = db.create_cpa_channel(
        name="CPA",
        base_url="https://proxy.example.com",
        management_key="secret",
    )
    db.record_cpa_quota_snapshot(
        channel.id,
        "account-hash",
        account_display="a***@example.com",
        plan="Plus",
        success=True,
        windows=[
            {
                "label": "5h Rolling",
                "used": 10,
                "remaining": 90,
                "total": 100,
                "unit": "%",
                "reset_at": "",
                "reset_in_sec": 0,
            }
        ],
    )
    db.record_cpa_channel_attempt(channel.id, success=True)

    public = TestClient(app).get("/api/public/quota")
    assert public.status_code == 200
    public_channel = public.json()["cpa_channels"][0]
    assert "id" not in public_channel
    assert "url" not in public_channel
    assert public_channel["accounts"][0]["account"] == "a***@example.com"
    assert "account_key_hash" not in public_channel["accounts"][0]

    db.update_cpa_channel(channel.id, enabled=False)
    assert TestClient(app).get("/api/public/quota").json()["cpa_channels"] == []
    assert len(db.list_cached_cpa_channels(enabled_only=False)[0]["accounts"]) == 1

    assert db.delete_cpa_channel(channel.id) is True
    with db.get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM cpa_quota_snapshots WHERE channel_id = ?",
            (channel.id,),
        ).fetchone()[0]
    assert count == 0


def test_cpa_write_requires_csrf(temp_data_dir):
    client = TestClient(app)
    login = client.post("/api/admin/auth/login", json={"token": ADMIN_TOKEN})
    assert login.status_code == 200
    response = client.post(
        "/api/admin/cpa/channels",
        json={
            "name": "CPA",
            "url": "https://proxy.example.com",
            "management_key": "secret",
        },
    )
    assert response.status_code == 403
