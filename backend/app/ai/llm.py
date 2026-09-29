
from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from ..config import settings


class QwenClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider

    def complete_json(self, system: str, user: str, image_url: str | None = None, model: str | None = None) -> dict[str, Any] | None:
        if self.provider not in {"qwen", "dashscope"}:
            return None
        if self.provider == "dashscope":
            base_url = settings.dashscope_base_url
            api_key = settings.dashscope_api_key
            selected_model = model or settings.dashscope_model
        else:
            base_url = settings.qwen_base_url
            api_key = settings.qwen_api_key
            selected_model = model or settings.qwen_model
        content: str | list[dict[str, Any]] = user
        if image_url:
            content = [
                {"type": "text", "text": user},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        payload = json.dumps({
            "model": selected_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }).encode()
        request = Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        try:
            with urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode())
            response_content = body["choices"][0]["message"]["content"]
            try:
                return json.loads(response_content)
            except json.JSONDecodeError:
                # Some compatible gateways wrap JSON in a Markdown code fence.
                start, end = response_content.find("{"), response_content.rfind("}")
                if start >= 0 and end > start:
                    return json.loads(response_content[start : end + 1])
                return None
        except Exception:
            # A local model being unavailable should not break a product demo.
            return None
