from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app import db
from app.bootstrap import ensure_bootstrapped


@pytest.fixture()
def temp_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("QUOTAHUB_DATA", str(data))
    monkeypatch.setenv("QUOTAHUB_ADMIN_TOKEN", "test-admin-token-with-at-least-32-characters")
    monkeypatch.setenv("QUOTAHUB_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    db.init_db()
    yield data
