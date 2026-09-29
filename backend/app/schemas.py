"""Request and response schemas for the HTTP API."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class RuleConfig(BaseModel):
    commission_min: float = Field(0.12, ge=0, le=1)
    shop_rating_min: float = Field(4.6, ge=0, le=5)
    return_rate_max: float = Field(0.12, ge=0, le=1)
    estimated_sales_min: int = Field(500, ge=0)
    ai_score_min: float = Field(60, ge=0, le=100)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=128)


class UserCreateRequest(LoginRequest):
    role: Literal["admin", "operator", "viewer"]


class RecommendRequest(BaseModel):
    hotspot_id: Optional[str] = None
    limit: int = Field(10, ge=1, le=50)
    rules: Optional[RuleConfig] = None


class FeedbackRequest(BaseModel):
    event_id: Optional[str] = None
    recommendation_id: Optional[str] = None
    product_id: str
    hotspot_id: Optional[str] = None
    impressions: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)
    orders: int = Field(..., ge=0)
    refunds: int = Field(0, ge=0)
    revenue: float = Field(..., ge=0)
    recorded_at: Optional[str] = None

    @model_validator(mode="after")
    def validate_funnel(self) -> "FeedbackRequest":
        if self.clicks > self.impressions:
            raise ValueError("点击数不能大于曝光数")
        if self.orders > self.clicks:
            raise ValueError("成交数不能大于点击数")
        if self.refunds > self.orders:
            raise ValueError("退款数不能大于成交数")
        return self


class SnapshotRequest(BaseModel):
    note: Optional[str] = None


class ContentDraftRequest(BaseModel):
    product_id: str
    hotspot_id: str
    recommendation_id: Optional[str] = None


class APIResponse(BaseModel):
    data: Any
    meta: dict[str, Any] = {}
