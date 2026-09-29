"""Backend orchestration and in-memory state for the local demo."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from .ai.pipeline import RecommendationPipeline
from .ai.model_registry import model_versions, runtime_models
from .ai.features import product_quality_stats
from .ai.llm import QwenClient
from .data import find_hotspot, find_product, load_hotspot_history, load_hotspots, load_products
from .integrations.runtime_store import JsonRuntimeStore, RuntimeStore
from .schemas import RuleConfig


class DemoService:
    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self.rules = RuleConfig()
        self.pipeline = RecommendationPipeline()
        self.runtime_store = runtime_store or JsonRuntimeStore()
        self.feedback: list[dict[str, Any]] = self.runtime_store.load_feedback()
        self.training_snapshots: list[dict[str, Any]] = self.runtime_store.load_training_snapshots()
        self.last_recommendation: dict[str, Any] | None = None
        self.qwen = QwenClient()

    def recommend(self, hotspot_id: str | None, rules: RuleConfig | None, limit: int) -> dict[str, Any]:
        active_rules = rules or self.rules
        if rules:
            self.rules = rules
        hotspots = load_hotspots()
        hotspot = find_hotspot(hotspot_id) if hotspot_id else hotspots[0]
        if not hotspot:
            raise ValueError(f"热点不存在: {hotspot_id}")
        result = self.pipeline.run(load_products(), hotspot, active_rules.model_dump(), limit)
        recommendation_id = f"rec-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
        for item in result["recommendations"]:
            item["recommendation_id"] = recommendation_id
        result["recommendation_id"] = recommendation_id
        result["hotspot"] = hotspot
        result["rules"] = active_rules.model_dump()
        result["model_versions"] = model_versions()
        result["models"] = runtime_models()
        result["score_weights"] = {"potential": 0.55, "semantic": 0.30, "multimodal": 0.15}
        self.last_recommendation = {"recommendation_id": recommendation_id, "hotspot_id": hotspot["hotspot_id"], "created_at": datetime.now().isoformat(timespec="seconds"), "passed_count": result["passed_count"]}
        return result

    def data_quality(self) -> dict[str, Any]:
        stats = product_quality_stats(load_products())
        stats["categories"] = sorted({row.get("category", "未知") for row in load_products()})
        stats["rule"] = "去重 → 刷单标记过滤 → 数值异常裁剪"
        return stats

    def create_content_draft(self, product_id: str, hotspot_id: str, recommendation_id: str | None = None) -> dict[str, Any]:
        product = find_product(product_id)
        hotspot = find_hotspot(hotspot_id)
        if not product:
            raise ValueError(f"商品不存在: {product_id}")
        if not hotspot:
            raise ValueError(f"热点不存在: {hotspot_id}")
        prompt = f"商品标题：{product['title']}。商品描述：{product.get('description', '')}。热点：{hotspot['keyword']}，{hotspot['description']}。请生成适合抖音图文带货的内容草稿，只输出JSON：title、cover_copy、slides（数组，每项包含image_direction和copy）、selling_points（数组）、risk_notes（数组）。"
        result = self.qwen.complete_json("你是合规的内容电商图文策划，只输出可执行JSON，不夸大功效。", prompt)
        fallback_result = {
            "title": f"{hotspot['keyword']}｜{product['title']}的3个实用场景",
            "cover_copy": f"忙碌生活里，把{product['title']}用在这3个场景，省心又好拍",
            "slides": [
                {"image_direction": "生活化场景图：展示使用前的痛点", "copy": "先说清楚谁会遇到这个问题"},
                {"image_direction": "商品细节图：展示材质、尺寸或包装", "copy": f"重点展示{product['title']}的核心卖点"},
                {"image_direction": "使用结果图：展示整理、搭配或食用后的状态", "copy": "用前后对比给出可验证的使用体验"},
            ],
            "selling_points": ["场景明确，容易拍成连续图文", "商品信息可在首图和第二张图完成解释", "适合用清单或前后对比组织内容"],
            "risk_notes": ["避免使用绝对化用语", "功效描述需以商品真实资质和详情页为准"],
            "source": "demo-template",
        }
        if not result or not isinstance(result.get("slides"), list):
            result = fallback_result
        slides = [
            {"image_direction": str(item.get("image_direction", "商品场景图")), "copy": str(item.get("copy", "补充商品使用场景和可验证信息"))}
            for item in result.get("slides", [])
            if isinstance(item, dict)
        ][:5]
        selling_points = [str(item) for item in result.get("selling_points", []) if str(item).strip()][:6]
        risk_notes = [str(item) for item in result.get("risk_notes", []) if str(item).strip()][:6]
        if not slides or not selling_points or not risk_notes:
            result = fallback_result
            slides = fallback_result["slides"]
            selling_points = fallback_result["selling_points"]
            risk_notes = fallback_result["risk_notes"]
        return {
            "draft_id": f"draft-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            "recommendation_id": recommendation_id,
            "product_id": product_id,
            "hotspot_id": hotspot_id,
            "product_title": product["title"],
            "hotspot_keyword": hotspot["keyword"],
            "model": "qwen" if result.get("source") != "demo-template" else "demo-template",
            "prompt_version": "content-draft-v1",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "quality_checks": {"has_title": bool(str(result.get("title", "")).strip()), "slide_count": len(slides), "has_risk_notes": bool(risk_notes)},
            "title": str(result.get("title", f"{hotspot['keyword']}｜{product['title']}内容草稿")),
            "cover_copy": str(result.get("cover_copy", "围绕真实使用场景组织首图文案")),
            "slides": slides,
            "selling_points": selling_points,
            "risk_notes": risk_notes,
            "source": result.get("source", "qwen"),
        }

    def add_feedback(self, sample: dict[str, Any]) -> dict[str, Any]:
        if not find_product(sample["product_id"]):
            raise ValueError(f"商品不存在: {sample['product_id']}")
        if sample.get("hotspot_id") and not find_hotspot(sample["hotspot_id"]):
            raise ValueError(f"热点不存在: {sample['hotspot_id']}")
        event_id = sample.get("event_id") or f"evt-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        if any(row.get("event_id") == event_id for row in self.feedback):
            return {"received": False, "duplicate": True, "event_id": event_id, "sample_count": len(self.feedback), "message": "重复事件已忽略"}
        sample = {**sample, "event_id": event_id, "refunds": sample.get("refunds", 0), "recorded_at": sample.get("recorded_at") or datetime.now().isoformat(timespec="seconds")}
        self.feedback.append(sample)
        self.runtime_store.append_feedback(sample)
        return {"received": True, "duplicate": False, "event_id": event_id, "sample_count": len(self.feedback), "record": sample, "message": "Demo回流样本已进入待训练队列"}

    def hotspot_trends(self, days: int = 7, category: str | None = None) -> dict[str, Any]:
        hotspots = load_hotspots()
        history = load_hotspot_history()
        available_dates = [date.fromisoformat(row["date"]) for row in history]
        anchor_date = max(available_dates) if available_dates else date.today()
        cutoff = anchor_date - timedelta(days=max(days - 1, 0))
        selected_ids = {row["hotspot_id"] for row in hotspots if not category or row["category"] == category}
        current = [row for row in hotspots if row["hotspot_id"] in selected_ids]
        points = [row for row in history if row["hotspot_id"] in selected_ids and date.fromisoformat(row["date"]) >= cutoff]
        by_hotspot: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point in sorted(points, key=lambda item: (item["date"], item["hotspot_id"])):
            by_hotspot[point["hotspot_id"]].append(point)
        ranked = sorted(current, key=lambda row: row["heat_value"], reverse=True)
        rank_map = {row["hotspot_id"]: index + 1 for index, row in enumerate(ranked)}
        decorated = []
        for row in ranked:
            status = "上升" if row["rise_rate"] >= 0.2 else "稳定" if row["rise_rate"] >= 0.05 else "下降"
            decorated.append({**row, "rank": rank_map[row["hotspot_id"]], "trend_status": status, "history": by_hotspot.get(row["hotspot_id"], [])})
        return {
            "summary": {
                "total_hotspots": len(decorated),
                "rising_count": sum(row["trend_status"] == "上升" for row in decorated),
                "top_heat": decorated[0]["heat_value"] if decorated else 0,
                "average_rise_rate": round(sum(row["rise_rate"] for row in decorated) / len(decorated), 4) if decorated else 0,
            },
            "hotspots": decorated,
            "series": self._merge_hotspot_series(by_hotspot),
            "range_days": days,
        }

    @staticmethod
    def _merge_hotspot_series(by_hotspot: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        dates = sorted({point["date"] for points in by_hotspot.values() for point in points})
        return [{"date": day, **{hotspot_id: next((point["heat_value"] for point in by_hotspot[hotspot_id] if point["date"] == day), None) for hotspot_id in by_hotspot}} for day in dates]

    def feedback_records(self, product_id: str | None = None, hotspot_id: str | None = None) -> list[dict[str, Any]]:
        rows = self.feedback
        if product_id:
            rows = [row for row in rows if row["product_id"] == product_id]
        if hotspot_id:
            rows = [row for row in rows if row.get("hotspot_id") == hotspot_id]
        products = {row["product_id"]: row for row in load_products()}
        result = []
        for row in rows:
            product = products.get(row["product_id"], {})
            impressions = row["impressions"]
            clicks = row["clicks"]
            orders = row["orders"]
            gmv = float(row.get("revenue", row.get("gmv", 0)))
            result.append({
                **row,
                "title": product.get("title", "未知商品"),
                "category": product.get("category", "未知类目"),
                "commission_rate": product.get("commission_rate", 0),
                "ctr": round(clicks / impressions, 4) if impressions else 0,
                "cvr": round(orders / clicks, 4) if clicks else 0,
                "refund_rate": round(row.get("refunds", 0) / orders, 4) if orders else 0,
                "estimated_commission": round(gmv * product.get("commission_rate", 0), 2),
            })
        return sorted(result, key=lambda row: row.get("recorded_at", ""), reverse=True)

    def feedback_summary(self, product_id: str | None = None, hotspot_id: str | None = None) -> dict[str, Any]:
        rows = self.feedback_records(product_id, hotspot_id)
        impressions = sum(row["impressions"] for row in rows)
        clicks = sum(row["clicks"] for row in rows)
        orders = sum(row["orders"] for row in rows)
        refunds = sum(row.get("refunds", 0) for row in rows)
        gmv = round(sum(float(row.get("revenue", 0)) for row in rows), 2)
        commission = round(sum(float(row.get("estimated_commission", 0)) for row in rows), 2)
        return {
            "record_count": len(rows),
            "impressions": impressions,
            "clicks": clicks,
            "orders": orders,
            "refunds": refunds,
            "gmv": gmv,
            "estimated_commission": commission,
            "ctr": round(clicks / impressions, 4) if impressions else 0,
            "cvr": round(orders / clicks, 4) if clicks else 0,
            "refund_rate": round(refunds / orders, 4) if orders else 0,
            "gmv_per_thousand_impressions": round(gmv / impressions * 1000, 2) if impressions else 0,
        }

    def feedback_trends(self, product_id: str | None = None, hotspot_id: str | None = None) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"impressions": 0, "clicks": 0, "orders": 0, "refunds": 0, "gmv": 0})
        for row in self.feedback_records(product_id, hotspot_id):
            day = str(row.get("recorded_at", ""))[:10]
            item = grouped[day]
            item["impressions"] += row["impressions"]
            item["clicks"] += row["clicks"]
            item["orders"] += row["orders"]
            item["refunds"] += row.get("refunds", 0)
            item["gmv"] += float(row.get("revenue", 0))
        return [{"date": day, **values, "ctr": round(values["clicks"] / values["impressions"], 4) if values["impressions"] else 0, "cvr": round(values["orders"] / values["clicks"], 4) if values["clicks"] else 0} for day, values in sorted(grouped.items())]

    def loop_status(self) -> dict[str, Any]:
        min_training_samples = 20
        sample_count = len(self.feedback)
        latest = max((row.get("recorded_at", "") for row in self.feedback), default="")
        return {
            "model_version": "demo-qwen-plus-weighted-v0.1",
            "feedback_sample_count": sample_count,
            "min_training_samples": min_training_samples,
            "training_ready": sample_count >= min_training_samples,
            "latest_feedback_at": latest,
            "last_recommendation": self.last_recommendation,
            "snapshot_count": len(self.training_snapshots),
            "next_action": "可以生成离线训练快照" if sample_count >= min_training_samples else f"还需积累 {min_training_samples - sample_count} 条回流样本",
        }

    def create_training_snapshot(self, note: str | None = None) -> dict[str, Any]:
        status = "ready" if len(self.feedback) >= 20 else "needs_more_data"
        summary = self.feedback_summary()
        snapshot = {
            "snapshot_id": f"snap-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:5]}",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "simulation": True,
            "note": note or "Demo 回流样本训练快照",
            "sample_count": len(self.feedback),
            "positive_order_rate": round(summary["orders"] / summary["impressions"], 5) if summary["impressions"] else 0,
            "class_balance": {"positive": summary["orders"], "unlabeled_or_negative": max(0, summary["impressions"] - summary["orders"])},
            "features": ["commission_rate", "shop_rating", "return_rate", "estimated_sales", "sales_growth", "historical_ctr", "historical_conversion"],
            "metrics": None if status != "ready" else {"pr_auc": 0.78, "top_k_hit_rate": 0.64, "ndcg": 0.71, "calibration_error": 0.08},
            "next_action": "继续积累回流样本" if status != "ready" else "进入 LightGBM 候选模型评审",
        }
        self.training_snapshots.insert(0, snapshot)
        self.runtime_store.append_training_snapshot(snapshot)
        return snapshot

    def list_training_snapshots(self) -> list[dict[str, Any]]:
        return self.training_snapshots


service = DemoService()
