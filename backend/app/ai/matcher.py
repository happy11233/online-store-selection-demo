"""Hotspot-product matching and topic generation."""

from __future__ import annotations

from typing import Any

from .features import token_set
from .llm import QwenClient


class SemanticMatcher:
    def __init__(self) -> None:
        self.qwen = QwenClient()

    def match(self, product: dict[str, Any], hotspot: dict[str, Any]) -> dict[str, Any]:
        user = f"商品：{product['title']}。描述：{product.get('description', '')}。热点：{hotspot['keyword']}，{hotspot['description']}。输出JSON包含match_score、reason、topic。"
        qwen_result = self.qwen.complete_json("你是内容电商语义匹配专家，只输出JSON。", user)
        if qwen_result and isinstance(qwen_result.get("match_score"), (int, float)):
            return {
                "match_score": round(max(0, min(100, float(qwen_result["match_score"]))), 1),
                "reason": str(qwen_result.get("reason", "模型未提供匹配理由")),
                "topic": str(qwen_result.get("topic", f"{hotspot['keyword']}｜{product['title']}使用场景")),
                "source": "qwen",
            }
        product_tokens = token_set(f"{product['title']} {product.get('description', '')}")
        hotspot_tokens = token_set(f"{hotspot['keyword']} {hotspot.get('description', '')}")
        overlap = len(product_tokens & hotspot_tokens) / max(1, len(hotspot_tokens))
        category_bonus = 0.28 if product.get("category") == hotspot.get("category") else 0
        score = min(100, round(35 + overlap * 45 + category_bonus * 100, 1))
        reason = "、".join([
            "类目一致" if category_bonus else "场景可迁移",
            "关键词覆盖热点语义" if overlap else "可用痛点叙事建立关联",
            "适合用清单或对比图表达",
        ])
        topic = f"{hotspot['keyword']}｜{product['title']}的3个高效使用场景"
        return {"match_score": score, "reason": reason, "topic": topic, "source": "demo-token-similarity"}
