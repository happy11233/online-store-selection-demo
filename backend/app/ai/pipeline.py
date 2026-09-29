"""Recommendation pipeline for a selected hotspot."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from .features import clean_products
from .matcher import SemanticMatcher
from .multimodal import image_text_match
from .scorer import ProductScorer


class RecommendationPipeline:
    def __init__(self) -> None:
        self.scorer = ProductScorer()
        self.matcher = SemanticMatcher()

    def run(self, products: list[dict[str, Any]], hotspot: dict[str, Any], rules: dict[str, Any], limit: int = 10) -> dict[str, Any]:
        started = perf_counter()
        cleaned = clean_products(products)
        candidates: list[dict[str, Any]] = []
        filtered: list[dict[str, str]] = []
        for product in cleaned:
            reason = self._rule_failure(product, rules)
            if reason:
                filtered.append({"product_id": product["product_id"], "reason": reason})
                continue
            score = self.scorer.score(product, hotspot)
            semantic = self.matcher.match(product, hotspot)
            visual = image_text_match(product, hotspot)
            final_score = round(max(0, min(100, score["score"] * 0.55 + semantic["match_score"] * 0.3 + visual["similarity"] * 100 * 0.15)), 1)
            if final_score < rules["ai_score_min"]:
                filtered.append({"product_id": product["product_id"], "reason": f"综合分低于{rules['ai_score_min']}"})
                continue
            candidates.append({
                **product,
                "ai_score": score["score"],
                "semantic_score": semantic["match_score"],
                "multimodal_score": round(visual["similarity"] * 100, 1),
                "final_score": final_score,
                "score_factors": score["factors"],
                "ai_advice": score["advice"],
                "match_reason": semantic["reason"],
                "content_topic": semantic["topic"],
                "image_description": visual["image_description"],
                "multimodal_model": visual["model"],
                "model_sources": {"potential": score.get("source"), "semantic": semantic.get("source"), "multimodal": visual.get("source")},
            })
        candidates.sort(key=lambda item: item["final_score"], reverse=True)
        fallback_count = sum(sum(source in {"demo", "demo-weighted-scorer", "demo-token-similarity"} for source in item["model_sources"].values()) for item in candidates)
        return {
            "recommendations": candidates[:limit],
            "filtered": filtered,
            "candidate_count": len(cleaned),
            "passed_count": len(candidates),
            "cleaning_removed": max(0, len(products) - len(cleaned)),
            "runtime": {"inference_ms": round((perf_counter() - started) * 1000, 1), "fallback_components": fallback_count},
        }

    @staticmethod
    def _rule_failure(product: dict[str, Any], rules: dict[str, Any]) -> str:
        checks = [
            (product["commission_rate"] < rules["commission_min"], f"佣金低于{rules['commission_min']:.0%}"),
            (product["shop_rating"] < rules["shop_rating_min"], f"店铺评分低于{rules['shop_rating_min']:.1f}"),
            (product["return_rate"] > rules["return_rate_max"], f"退货率高于{rules['return_rate_max']:.0%}"),
            (product["estimated_sales"] < rules["estimated_sales_min"], f"预估销量低于{rules['estimated_sales_min']}"),
        ]
        return next((message for failed, message in checks if failed), "")
