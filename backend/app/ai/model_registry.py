"""Runtime model metadata for inference traces."""

from __future__ import annotations

from typing import Any

from ..config import settings


def runtime_models() -> list[dict[str, Any]]:
    text_model = settings.dashscope_model if settings.llm_provider == "dashscope" else settings.qwen_model
    vision_model = settings.dashscope_vision_model if settings.llm_provider == "dashscope" else "demo-image-caption+text-similarity"
    configured = settings.llm_provider == "demo" or bool(settings.dashscope_api_key if settings.llm_provider == "dashscope" else settings.qwen_api_key)
    return [
        {"role": "文本理解与选题", "model": text_model, "provider": settings.llm_provider, "version": "text-v1", "status": "active" if configured else "fallback", "configured": configured},
        {"role": "结构化潜力预测", "model": "demo-weighted-scorer", "provider": "demo", "version": "potential-v0.1", "status": "fallback", "production_target": "LightGBM"},
        {"role": "图片热点匹配", "model": vision_model, "provider": settings.llm_provider if settings.llm_provider == "dashscope" else "demo", "version": "vision-v1", "status": "active" if configured else "fallback", "configured": configured},
    ]


def model_versions() -> dict[str, str]:
    return {item["role"]: item["version"] for item in runtime_models()}
