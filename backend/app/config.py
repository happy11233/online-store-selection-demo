"""Configuration kept deliberately small for a local demo."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


# Local secrets live in the repository-root .env and are never committed.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "AIMid 内容带货选品系统"
    data_dir: str = os.getenv("AIMID_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
    app_env: str = os.getenv("AIMID_ENV", "demo")
    secure_cookies: bool = os.getenv("AIMID_SECURE_COOKIES", "0") == "1"
    # demo: no network call; qwen: local endpoint; dashscope: Alibaba Bailian.
    llm_provider: str = os.getenv("LLM_PROVIDER", "demo")
    qwen_base_url: str = os.getenv("QWEN_BASE_URL", "http://127.0.0.1:8000/v1")
    qwen_model: str = os.getenv("QWEN_MODEL", "Qwen2.5-7B-Instruct")
    qwen_api_key: str = os.getenv("QWEN_API_KEY", "EMPTY")
    dashscope_base_url: str = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    dashscope_model: str = os.getenv("DASHSCOPE_MODEL", "qwen3.8-flash")
    dashscope_vision_model: str = os.getenv("DASHSCOPE_VISION_MODEL", "qwen-vl-plus")
    dashscope_api_key: str = os.getenv("DASHSCOPE_API_KEY", "")


settings = Settings()
