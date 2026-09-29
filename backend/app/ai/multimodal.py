"""Image-scene matching for offline and configured model modes.

Production uses CLIP/Alibaba multimodal models. Demo maps sample image URLs to
descriptions and calculates text similarity, so it remains offline and testable.
"""

from __future__ import annotations

from typing import Any

from .features import token_set
from .llm import QwenClient
from ..config import settings


IMAGE_DESCRIPTIONS = {
    "家居百货": "明亮厨房收纳场景，白色台面，整洁实用，展示前后对比",
    "食品饮料": "自然光零食开箱场景，桌面摆放多种口味，适合分享推荐",
    "美妆个护": "干净浴室和护肤产品特写，清爽质地，突出使用步骤",
    "服饰": "日常通勤穿搭场景，人物上身效果，简洁有质感",
    "数码": "桌面办公设备特写，科技感和效率提升场景",
}


def image_text_match(product: dict[str, Any], hotspot: dict[str, Any]) -> dict[str, Any]:
    if settings.llm_provider == "dashscope" and product.get("image_url"):
        result = QwenClient().complete_json(
            "你是商品图片与热点场景匹配专家，只输出JSON。",
            f"识别图片内容，并判断它和热点“{hotspot['keyword']}”的适配度。输出 image_description、similarity（0到1）、reason。",
            image_url=product["image_url"],
            model=settings.dashscope_vision_model,
        )
        if result and isinstance(result.get("similarity"), (int, float)):
            return {
                "image_description": result.get("image_description", "模型未提供图片描述"),
                "similarity": round(max(0, min(1, float(result["similarity"]))), 3),
                "model": settings.dashscope_vision_model,
                "source": "dashscope",
            }
    description = IMAGE_DESCRIPTIONS.get(product.get("category"), "商品主体清晰，生活化使用场景")
    image_tokens = token_set(description)
    hot_tokens = token_set(f"{hotspot['keyword']} {hotspot.get('description', '')}")
    similarity = len(image_tokens & hot_tokens) / max(1, len(image_tokens | hot_tokens))
    # category alignment provides the visual-scene prior in this simplified demo.
    if product.get("category") == hotspot.get("category"):
        similarity = min(1, similarity + 0.18)
    return {"image_description": description, "similarity": round(similarity, 3), "model": "demo-image-caption+text-similarity", "source": "demo"}
