"""Security and mock connector contracts, isolated from the user's data files."""

import socket
import sqlite3

from fastapi.testclient import TestClient

from app import main as main_module
from app.data import load_hotspots, load_products
from app.integrations.source_service import DataSourceService


def login_as(client: TestClient, username: str, password: str) -> TestClient:
    user_client = TestClient(main_module.app)
    response = user_client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    user_client.headers["X-CSRF-Token"] = response.json()["data"]["csrf_token"]
    return user_client


def test_unauthenticated_requests_are_protected(client: TestClient) -> None:
    anonymous = TestClient(main_module.app)
    assert anonymous.get("/api/health").status_code == 200
    assert anonymous.get("/api/auth/status").json()["data"]["initialized"] is True
    for path in ("/api/auth/me", "/api/products", "/api/data-sources", "/api/recommendations/export"):
        assert anonymous.get(path).status_code == 401
    assert anonymous.post("/api/recommendations", json={}).status_code == 401
    assert client.post("/api/auth/bootstrap", json={"username": "another", "password": "AnotherDemo123!"}).status_code == 409


def test_csrf_roles_and_logout(client: TestClient) -> None:
    payload = {"username": "viewer_1", "password": "ViewerDemoPass123!", "role": "viewer"}
    assert client.post("/api/auth/users", json=payload).status_code == 200
    operator = {"username": "operator_1", "password": "OperatorDemoPass123!", "role": "operator"}
    assert client.post("/api/auth/users", json=operator).status_code == 200

    assert client.put("/api/rules", json={"commission_min": 0.1}, headers={"X-CSRF-Token": "invalid"}).status_code == 403
    viewer = login_as(client, payload["username"], payload["password"])
    assert viewer.get("/api/products").status_code == 200
    assert viewer.get("/api/recommendations/export").status_code == 403
    assert viewer.post("/api/recommendations", json={}).status_code == 403
    assert viewer.get("/api/auth/users").status_code == 403
    assert viewer.post("/api/data-sources/products/connect").status_code == 403

    ops = login_as(client, operator["username"], operator["password"])
    assert ops.post("/api/recommendations", json={"hotspot_id": "H2002"}).status_code == 200
    assert ops.put("/api/rules", json={"commission_min": 0.1}).status_code == 403
    assert ops.post("/api/data-sources/products/connect").status_code == 403
    assert ops.post("/api/auth/logout").status_code == 200
    assert ops.get("/api/auth/me").status_code == 401


def test_expired_session_and_login_limit(client: TestClient) -> None:
    with sqlite3.connect(main_module.auth_store.path) as db:
        db.execute("UPDATE sessions SET expires_at = 1")
    assert client.get("/api/auth/me").status_code == 401

    anonymous = TestClient(main_module.app)
    body = {"username": "testadmin", "password": "WrongPassword123!"}
    for _ in range(5):
        assert anonymous.post("/api/auth/login", json=body).status_code == 401
    assert anonymous.post("/api/auth/login", json=body).status_code == 429


def test_mock_connect_sync_and_snapshot(client: TestClient) -> None:
    initial = client.get("/api/data-sources").json()["data"]
    assert [row["resource"] for row in initial] == ["products", "hotspots"]
    assert all(row["status"] == "not_connected" for row in initial)
    assert client.post("/api/data-sources/products/sync").status_code == 409

    for resource, count in (("products", 8), ("hotspots", 4)):
        assert client.post(f"/api/data-sources/{resource}/connect").status_code == 200
        sync = client.post(f"/api/data-sources/{resource}/sync")
        assert sync.status_code == 200, sync.text
        state = sync.json()["data"]
        assert state["status"] == "synced"
        assert state["record_count"] == count
        assert state["snapshot_id"].startswith(f"mock-{resource}-")
    assert load_products()[0]["source_type"] == "mock"
    assert load_hotspots()[0]["source_type"] == "mock"
    restarted = DataSourceService(main_module.source_service.data_dir)
    assert all(row["status"] == "synced" for row in restarted.list_sources())
    assert client.post("/api/recommendations", json={"hotspot_id": "H2002"}).status_code == 200
    assert client.post("/api/data-sources/unknown/connect").status_code == 404


def test_sync_rejects_missing_fields_without_fabricating_values(client: TestClient, monkeypatch) -> None:
    client.post("/api/data-sources/products/connect")
    baseline = load_products()[0]
    monkeypatch.setattr(main_module.source_service.adapter, "fetch_products", lambda: [{**baseline, "product_id": "P-new"}, {"product_id": "P-bad", "title": "broken"}, {**baseline, "product_id": "P-new"}, {**baseline, "product_id": "P-negative", "price": -1}])
    result = client.post("/api/data-sources/products/sync")
    assert result.status_code == 200
    assert result.json()["data"]["record_count"] == 1
    assert result.json()["data"]["rejected_count"] == 3
    assert load_products()[0]["price"] == baseline["price"]

    monkeypatch.setattr(main_module.source_service.adapter, "fetch_products", lambda: [{"product_id": "P-only"}])
    failed = client.post("/api/data-sources/products/sync")
    assert failed.status_code == 409
    assert len(load_products()) == 1  # Previous valid snapshot is preserved.
    assert client.get("/api/data-sources").json()["data"][0]["status"] == "error"


def test_official_entry_never_issues_network_request(client: TestClient, monkeypatch) -> None:
    def forbid_network(*args, **kwargs):
        raise AssertionError("Demo attempted an outbound platform request")

    monkeypatch.setattr(socket, "create_connection", forbid_network)
    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    status = client.get("/api/integrations/douyin/status")
    assert status.status_code == 200
    assert status.json()["data"]["enabled"] is False
    assert status.json()["data"]["outbound_requests"] is False
    assert client.post("/api/integrations/douyin/authorize").status_code == 409
    assert client.post("/api/integrations/douyin/sync").status_code == 409
