"""Product potential scoring."""

from __future__ import annotations

from typing import Any

import math

from .features import build_features
from .llm import QwenClient


class ProductScorer:
    def __init__(self) -> None:
        self.qwen = QwenClient()

    def score(self, product: dict[str, Any], hotspot: dict[str, Any] | None = None) -> dict[str, Any]:
        features = build_features([product]).iloc[0].to_dict()
        # A single-row Demo inference has no batch maximum; use a stable sales
        # reference so scores remain comparable across recommendation requests.
        features["sales_score"] = min(1.0, math.log1p(float(product.get("estimated_sales", 0))) / math.log1p(50000))
        hotspot_text = (hotspot or {}).get("keyword", "泛生活好物")
        qwen_result = self.qwen.complete_json(
            "你是抖音图文带货选品分析师，只输出JSON。",
            f"分析商品{product['title']}和热点{hotspot_text}，给出0到100的图文转化潜力分、三个因素和一句建议。",
        )
        if qwen_result and isinstance(qwen_result.get("score"), (int, float)):
            factors = qwen_result.get("factors", [])
            return {
                "score": round(max(0, min(100, float(qwen_result["score"]))), 1),
                "factors": [str(item) for item in factors if str(item).strip()][:5] if isinstance(factors, list) else [],
                "advice": str(qwen_result.get("advice", "")),
                "source": "qwen",
            }
        # Demo LLM simulation: weighted reasoning features, intentionally explainable.
        score = (
            features.get("commission_score", 0) * 18
            + features.get("rating_score", 0) * 15
            + features.get("return_score", 0) * 18
            + features.get("sales_score", 0) * 16
            + features.get("growth_score", 0) * 13
            + features.get("content_score", 0) * 20
        )
        factors = [
            f"佣金{product['commission_rate']:.0%}，内容收益空间{'较高' if product['commission_rate'] >= 0.15 else '一般'}",
            f"店铺评分{product['shop_rating']:.1f}分、退货率{product['return_rate']:.0%}",
            f"历史图文转化率{features.get('historical_conversion', 0):.1%}，销量增速{product.get('sales_growth', 0):.0%}",
        ]
        advice = f"围绕“{hotspot_text}”突出使用场景和前后对比，首图建议先展示核心结果。"
        return {"score": round(max(0, min(100, score)), 1), "factors": factors, "advice": advice, "source": "demo-weighted-scorer"}
