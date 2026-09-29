"""Product data cleaning and feature extraction."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate ids, malformed rows and obvious simulated刷单 samples."""
    frame = pd.DataFrame(products)
    if frame.empty:
        return []
    frame = frame.drop_duplicates(subset=["product_id"]).copy()
    frame = frame[frame["is_fraud_suspect"].fillna(False) == False]  # noqa: E712
    for column in ["price", "commission_rate", "estimated_sales", "return_rate", "shop_rating", "sales_growth"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["price"] = frame["price"].clip(lower=0)
    frame["commission_rate"] = frame["commission_rate"].clip(0, 1)
    frame["return_rate"] = frame["return_rate"].clip(0, 1)
    frame["shop_rating"] = frame["shop_rating"].clip(0, 5)
    frame["estimated_sales"] = frame["estimated_sales"].clip(lower=0)
    frame["sales_growth"] = frame["sales_growth"].clip(-1, 10)
    return frame.to_dict(orient="records")


def product_quality_stats(products: list[dict[str, Any]]) -> dict[str, Any]:
    """Return explainable cleaning counts for the operations dashboard."""
    ids = [row.get("product_id") for row in products]
    duplicate_count = len(ids) - len(set(ids))
    fraud_count = sum(bool(row.get("is_fraud_suspect")) for row in products)
    anomaly_count = 0
    for row in products:
        try:
            invalid = (
                float(row.get("price", 0)) < 0
                or not 0 <= float(row.get("commission_rate", 0)) <= 1
                or not 0 <= float(row.get("return_rate", 0)) <= 1
                or not 0 <= float(row.get("shop_rating", 0)) <= 5
            )
        except (TypeError, ValueError):
            invalid = True
        anomaly_count += int(invalid)
    cleaned = clean_products(products)
    return {
        "raw_count": len(products),
        "duplicate_count": duplicate_count,
        "fraud_suspect_count": fraud_count,
        "anomaly_count": anomaly_count,
        "cleaned_count": len(cleaned),
        "removed_count": len(products) - len(cleaned),
        "quality_rate": round(len(cleaned) / len(products), 4) if products else 0,
    }


def build_features(products: list[dict[str, Any]]) -> pd.DataFrame:
    """Build normalized structured features used by Demo LLM scoring."""
    frame = pd.DataFrame(products)
    if frame.empty:
        return frame
    hist = frame["historical_content_metrics"].apply(lambda x: x if isinstance(x, dict) else {})
    frame["historical_ctr"] = hist.apply(lambda x: _safe_float(x.get("ctr")))
    frame["historical_conversion"] = hist.apply(lambda x: _safe_float(x.get("conversion_rate")))
    frame["title_tokens"] = frame.apply(lambda row: token_set(f'{row.get("title", "")} {row.get("description", "")}'), axis=1)
    frame["commission_score"] = frame["commission_rate"].clip(0, 0.3) / 0.3
    frame["rating_score"] = frame["shop_rating"] / 5
    frame["return_score"] = 1 - frame["return_rate"]
    frame["sales_score"] = np.log1p(frame["estimated_sales"]) / np.log1p(max(float(frame["estimated_sales"].max()), 1))
    frame["growth_score"] = ((frame["sales_growth"] + 0.2) / 1.2).clip(0, 1)
    frame["content_score"] = (frame["historical_ctr"].clip(0, 0.2) / 0.2 * 0.5 + frame["historical_conversion"].clip(0, 0.2) / 0.2 * 0.5)
    return frame


def token_set(text: str) -> set[str]:
    """Tiny tokenization fallback; production can replace with Chinese tokenizer/embedding."""
    text = str(text).lower()
    words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text)
    # Chinese character bigrams retain enough signal for this local demo.
    joined = "".join(words)
    bigrams = {joined[index : index + 2] for index in range(max(0, len(joined) - 1))}
    return set(words) | bigrams
