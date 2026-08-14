from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app


def _login(client: TestClient):
    return client.post(
        "/api/admin/auth/login",
        json={"token": "test-admin-token-with-at-least-32-characters"},
    )


def test_admin_routes_require_session(temp_data_dir):
    client = TestClient(app)
    assert client.get("/api/admin/config").status_code == 401
    assert client.get("/api/admin/accounts/opencode").status_code == 401
    assert client.get("/api/admin/usage/all").status_code == 401


def test_login_session_csrf_and_logout(temp_data_dir):
    client = TestClient(app)
    login = _login(client)
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    assert login.cookies.get(auth.SESSION_COOKIE)
    assert login.cookies.get(auth.CSRF_COOKIE) == csrf
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]

    assert client.get("/api/admin/auth/session").status_code == 200
    assert client.put("/api/admin/config", json={}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.put("/api/admin/config", json={}).status_code == 200
    assert client.post("/api/admin/auth/logout").status_code == 200
    assert client.get("/api/admin/auth/session").status_code == 401


def test_invalid_login_is_throttled(temp_data_dir):
    first_client = TestClient(app)
    second_client = TestClient(app)
    for index in range(auth.LOGIN_MAX_FAILURES):
        client = first_client if index % 2 == 0 else second_client
        assert client.post("/api/admin/auth/login", json={"token": "wrong"}).status_code == 401
    assert second_client.post("/api/admin/auth/login", json={"token": "wrong"}).status_code == 429
    assert _login(second_client).status_code == 429

    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT source_hmac FROM admin_login_attempts"
        ).fetchall()
    assert len(rows) == auth.LOGIN_MAX_FAILURES
    assert all(row["source_hmac"].startswith("hmac:v1:") for row in rows)
    assert all(row["source_hmac"] != "testclient" for row in rows)


def test_concurrent_login_failures_are_recorded_atomically(temp_data_dir):
    source_hmac = "hmac:v1:" + "a" * 64
    now = datetime.now(UTC)
    cutoff = (now - auth.LOGIN_WINDOW).isoformat().replace("+00:00", "Z")
    attempted_at = now.isoformat().replace("+00:00", "Z")
    barrier = Barrier(10)

    def attempt() -> tuple[bool, int]:
        barrier.wait()
        return db.apply_admin_login_attempt(
            source_hmac,
            success=False,
            cutoff_iso=cutoff,
            attempted_at=attempted_at,
            max_failures=auth.LOGIN_MAX_FAILURES,
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _index: attempt(), range(10)))

    assert sum(allowed for allowed, _count in results) == auth.LOGIN_MAX_FAILURES
    with db.get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM admin_login_attempts WHERE source_hmac = ?",
            (source_hmac,),
        ).fetchone()[0]
    assert count == auth.LOGIN_MAX_FAILURES


def test_successful_login_clears_persisted_failures(temp_data_dir):
    client = TestClient(app)
    assert client.post("/api/admin/auth/login", json={"token": "wrong"}).status_code == 401
    assert _login(client).status_code == 200
    with db.get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM admin_login_attempts").fetchone()[0] == 0


def test_expired_session_is_rejected(temp_data_dir):
    raw = "expired-session-token"
    token_hash = auth._token_hash(raw)
    expires = (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    db.create_admin_session(token_hash, expires)
    client = TestClient(app)
    client.cookies.set(auth.SESSION_COOKIE, raw)
    assert client.get("/api/admin/auth/session").status_code == 401
    assert db.get_admin_session(token_hash) is None


def test_legacy_management_paths_are_not_available(temp_data_dir):
    client = TestClient(app)
    assert client.get("/api/config").status_code == 404
    assert client.get("/api/accounts/opencode").status_code == 404
    assert client.get("/api/usage/all").status_code == 404
