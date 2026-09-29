"""Connection and snapshot lifecycle for local mock data sources."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from ..config import settings
from .douyin_client import MockCommerceDataSource

SOURCES = {
    "products": {"label": "商品数据", "id_field": "product_id", "required": ("product_id", "title", "description", "image_url", "category", "price", "commission_rate", "estimated_sales", "return_rate", "shop_rating", "sales_growth", "is_fraud_suspect", "historical_content_metrics")},
    "hotspots": {"label": "热点数据", "id_field": "hotspot_id", "required": ("hotspot_id", "keyword", "category", "description", "heat_value", "rise_rate")},
}


class DataSourceService:
    def __init__(self, data_dir: Path | None = None, adapter: MockCommerceDataSource | None = None) -> None:
        self.data_dir = data_dir or Path(settings.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.adapter = adapter or MockCommerceDataSource()
        self.lock = Lock()
        self.state_path = self.data_dir / "data_sources_runtime.json"

    def _read_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {}

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _normalize(resource: str, row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        if any(key not in row or row[key] is None or row[key] == "" for key in SOURCES[resource]["required"]):
            return None
        clean = dict(row)
        text_fields = ("product_id", "title", "description", "image_url", "category") if resource == "products" else ("hotspot_id", "keyword", "description", "category")
        for field in text_fields:
            if not isinstance(clean[field], str) or not clean[field].strip():
                return None
            clean[field] = clean[field].strip()
        number_fields = ("price", "commission_rate", "estimated_sales", "return_rate", "shop_rating", "sales_growth") if resource == "products" else ("heat_value", "rise_rate")
        for field in number_fields:
            if isinstance(clean[field], bool):
                return None
            try:
                clean[field] = float(clean[field])
            except (TypeError, ValueError):
                return None
            if not math.isfinite(clean[field]):
                return None
        if resource == "products":
            if not (clean["price"] > 0 and 0 <= clean["commission_rate"] <= 1 and clean["estimated_sales"] >= 0 and clean["estimated_sales"].is_integer() and 0 <= clean["return_rate"] <= 1 and 0 <= clean["shop_rating"] <= 5 and -1 <= clean["sales_growth"] <= 10):
                return None
            if not isinstance(clean["is_fraud_suspect"], bool) or not isinstance(clean["historical_content_metrics"], dict):
                return None
            clean["estimated_sales"] = int(clean["estimated_sales"])
        elif not (0 <= clean["heat_value"] <= 100 and -1 <= clean["rise_rate"] <= 10):
            return None
        clean["source_type"] = "mock"
        return clean

    def list_sources(self) -> list[dict[str, Any]]:
        with self.lock:
            state = self._read_state()
            result = []
            for resource, spec in SOURCES.items():
                entry = state.get(resource, {})
                result.append({
                    "resource": resource, "label": spec["label"], "mode": "mock",
                    "connected": entry.get("connected", False),
                    "status": entry.get("status", "not_connected"),
                    "last_success_at": entry.get("last_success_at"),
                    "record_count": entry.get("record_count"),
                    "rejected_count": entry.get("rejected_count"),
                    "last_error": entry.get("last_error"),
                    "snapshot_id": entry.get("snapshot_id"),
                })
            return result

    def connect(self, resource: str) -> dict[str, Any]:
        if resource not in SOURCES:
            raise KeyError(resource)
        with self.lock:
            state = self._read_state()
            state[resource] = {**state.get(resource, {}), "connected": True, "status": "connected", "last_error": None}
            self._write_json(self.state_path, state)
        return next(row for row in self.list_sources() if row["resource"] == resource)

    def sync(self, resource: str) -> dict[str, Any]:
        if resource not in SOURCES:
            raise KeyError(resource)
        with self.lock:
            state = self._read_state()
            if not state.get(resource, {}).get("connected"):
                raise ValueError("请先连接模拟数据源")
            try:
                raw = self.adapter.fetch_products() if resource == "products" else self.adapter.fetch_hotspots()
                if not isinstance(raw, list):
                    raise ValueError("数据源返回格式错误")
                id_field = SOURCES[resource]["id_field"]
                seen: set[str] = set()
                clean: list[dict[str, Any]] = []
                rejected = 0
                for row in raw:
                    normalized = self._normalize(resource, row)
                    if normalized is None:
                        rejected += 1
                        continue
                    identifier = str(normalized[id_field])
                    if identifier in seen:
                        rejected += 1
                        continue
                    seen.add(identifier)
                    clean.append(normalized)
                if not clean:
                    raise ValueError("没有可用记录，已保留上次快照")
                snapshot_id = f"mock-{resource}-{uuid4().hex[:10]}"
                self._write_json(self.data_dir / f"sync_{resource}_runtime.json", clean)
                state[resource] = {"connected": True, "status": "synced", "last_success_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "record_count": len(clean), "rejected_count": rejected, "snapshot_id": snapshot_id, "last_error": None}
            except Exception as error:
                state[resource] = {**state[resource], "status": "error", "last_error": str(error)}
                self._write_json(self.state_path, state)
                raise
            self._write_json(self.state_path, state)
        return next(row for row in self.list_sources() if row["resource"] == resource)


source_service = DataSourceService()
