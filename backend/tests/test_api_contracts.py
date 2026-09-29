from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.ai.llm import QwenClient


def test_health_and_model_metadata_are_safe(client: TestClient) -> None:
    health = client.get("/api/health")
    models = client.get("/api/models")

    assert health.status_code == 200
    assert health.json()["real_douyin_api"] is False
    assert models.status_code == 200
    assert models.json()["meta"]["credentials_exposed"] is False
    assert all("api_key" not in item for item in models.json()["data"])


def test_data_quality_and_recommendation_contract(client: TestClient) -> None:
    quality = client.get("/api/data-quality").json()["data"]
    assert quality["raw_count"] == 8
    assert quality["cleaned_count"] == 7
    assert quality["fraud_suspect_count"] == 1

    response = client.post("/api/recommendations", json={"hotspot_id": "H2002", "limit": 10})
    payload = response.json()["data"]
    assert response.status_code == 200
    assert payload["candidate_count"] == 7
    assert payload["cleaning_removed"] == 1
    assert payload["filtered"]
    assert all(0 <= row["final_score"] <= 100 for row in payload["recommendations"])
    assert all("product_id" in row and "reason" in row for row in payload["filtered"])


def test_content_draft_uses_validated_fallback(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(QwenClient, "complete_json", lambda *args, **kwargs: None)
    response = client.post("/api/content-drafts", json={"product_id": "P1002", "hotspot_id": "H2002"})
    draft = response.json()["data"]

    assert response.status_code == 200
    assert draft["model"] == "demo-template"
    assert draft["prompt_version"] == "content-draft-v1"
    assert draft["quality_checks"] == {"has_title": True, "slide_count": 3, "has_risk_notes": True}
    assert len(draft["slides"]) == 3


def test_feedback_funnel_and_duplicate_event(client: TestClient) -> None:
    invalid = client.post(
        "/api/feedback",
        json={"product_id": "P1002", "impressions": 10, "clicks": 11, "orders": 1, "revenue": 39.9},
    )
    assert invalid.status_code == 422

    event_id = f"contract-{uuid4().hex}"
    body = {"event_id": event_id, "product_id": "P1002", "hotspot_id": "H2002", "impressions": 1000, "clicks": 100, "orders": 10, "refunds": 1, "revenue": 399.0}
    accepted = client.post("/api/feedback", json=body)
    duplicate = client.post("/api/feedback", json=body)
    assert accepted.status_code == 200
    assert accepted.json()["data"]["received"] is True
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["duplicate"] is True


def test_training_snapshot_is_visible_in_loop_contract(client: TestClient) -> None:
    created = client.post("/api/loop/snapshots", json={"note": "contract test"})
    listed = client.get("/api/loop/snapshots")

    assert created.status_code == 200
    snapshot = created.json()["data"]
    assert snapshot["simulation"] is True
    assert snapshot["status"] in {"needs_more_data", "ready"}
    assert listed.json()["data"][0]["snapshot_id"] == snapshot["snapshot_id"]


def test_recommendation_export_is_csv(client: TestClient) -> None:
    response = client.get("/api/recommendations/export?hotspot_id=H2002")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "product_id,title" in response.content.decode("utf-8-sig")
