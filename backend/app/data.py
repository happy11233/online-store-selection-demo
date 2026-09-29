"""Local JSON data source.  Replace this repository with MySQL/Redis adapters in production."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import settings


def _read_json(filename: str) -> list[dict[str, Any]]:
    with Path(settings.data_dir, filename).open(encoding="utf-8") as stream:
        return json.load(stream)


def load_mock_products() -> list[dict[str, Any]]:
    return _read_json("products.json")


def load_mock_hotspots() -> list[dict[str, Any]]:
    return _read_json("hotspots.json")


def load_products() -> list[dict[str, Any]]:
    path = Path(settings.data_dir, "sync_products_runtime.json")
    return _read_json(path.name if path.exists() else "products.json")


def load_hotspots() -> list[dict[str, Any]]:
    path = Path(settings.data_dir, "sync_hotspots_runtime.json")
    return _read_json(path.name if path.exists() else "hotspots.json")


def load_hotspot_history() -> list[dict[str, Any]]:
    return _read_json("hotspot_history.json")


def load_feedback() -> list[dict[str, Any]]:
    seed = _read_json("feedback.json")
    runtime_path = Path(settings.data_dir, "feedback_runtime.json")
    if not runtime_path.exists():
        return seed
    with runtime_path.open(encoding="utf-8") as stream:
        return seed + json.load(stream)


def load_training_snapshots() -> list[dict[str, Any]]:
    """Load Demo snapshots while keeping the checked-in seed data immutable."""
    runtime_path = Path(settings.data_dir, "training_snapshots_runtime.json")
    if not runtime_path.exists():
        return []
    with runtime_path.open(encoding="utf-8") as stream:
        return json.load(stream)


def append_feedback(sample: dict[str, Any]) -> None:
    runtime_path = Path(settings.data_dir, "feedback_runtime.json")
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if runtime_path.exists():
        with runtime_path.open(encoding="utf-8") as stream:
            existing = json.load(stream)
    existing.append(sample)
    runtime_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def append_training_snapshot(snapshot: dict[str, Any]) -> None:
    runtime_path = Path(settings.data_dir, "training_snapshots_runtime.json")
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_training_snapshots()
    existing.insert(0, snapshot)
    runtime_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def find_product(product_id: str) -> dict[str, Any] | None:
    return next((item for item in load_products() if item["product_id"] == product_id), None)


def find_hotspot(hotspot_id: str) -> dict[str, Any] | None:
    return next((item for item in load_hotspots() if item["hotspot_id"] == hotspot_id), None)
