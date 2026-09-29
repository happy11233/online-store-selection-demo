from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Configure isolated seed data before the application imports settings/auth stores.
TEST_DATA = tempfile.TemporaryDirectory(prefix="aimid-pytest-")
SEED_DATA = Path(__file__).resolve().parents[1] / "data"
for filename in ("products.json", "hotspots.json", "hotspot_history.json", "feedback.json"):
    shutil.copy2(SEED_DATA / filename, Path(TEST_DATA.name) / filename)
os.environ["AIMID_DATA_DIR"] = TEST_DATA.name
os.environ["AIMID_ENV"] = "demo"
os.environ["LLM_PROVIDER"] = "demo"

from app.auth import AuthStore  # noqa: E402
from app.main import app
from app import main as main_module
from app import data as data_module
from app import services as service_module
from app.ai.llm import QwenClient
from app.config import settings
from app.integrations.source_service import DataSourceService


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    """Keep API tests offline and prevent runtime JSON files from being changed."""
    monkeypatch.setattr(QwenClient, "complete_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(main_module, "auth_store", AuthStore(tmp_path / "auth.sqlite3"))
    source_dir = tmp_path / "data"
    source_dir.mkdir()
    for filename in ("products.json", "hotspots.json", "hotspot_history.json", "feedback.json"):
        shutil.copy2(SEED_DATA / filename, source_dir / filename)
    monkeypatch.setattr(data_module, "settings", replace(settings, data_dir=str(source_dir)))
    monkeypatch.setattr(main_module, "source_service", DataSourceService(source_dir))
    monkeypatch.setattr(service_module.service.runtime_store, "append_feedback", lambda sample: None)
    monkeypatch.setattr(service_module.service.runtime_store, "append_training_snapshot", lambda snapshot: None)
    original_feedback = service_module.service.feedback
    original_snapshots = service_module.service.training_snapshots
    service_module.service.feedback = list(original_feedback)
    service_module.service.training_snapshots = list(original_snapshots)
    with TestClient(app) as session_client:
        initialized = session_client.post("/api/auth/bootstrap", json={"username": "testadmin", "password": "LocalDemoPass123!"})
        assert initialized.status_code == 200, initialized.text
        session_client.headers["X-CSRF-Token"] = initialized.json()["data"]["csrf_token"]
        yield session_client
    service_module.service.feedback = original_feedback
    service_module.service.training_snapshots = original_snapshots
