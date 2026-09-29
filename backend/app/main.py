"""HTTP routes for the selection console."""

from __future__ import annotations

import csv
import io

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .config import settings
from .data import find_hotspot, find_product, load_hotspots, load_products
from .ai.model_registry import runtime_models
from .auth import COOKIE_NAME, ROLE_LEVEL, SESSION_TTL_SECONDS, auth_store, csrf_valid
from .schemas import ContentDraftRequest, FeedbackRequest, LoginRequest, RecommendRequest, RuleConfig, SnapshotRequest, UserCreateRequest
from .services import service
from .integrations.source_service import source_service

app = FastAPI(title=settings.app_name, version="0.2.0", description="本地模拟数据 Demo，不连接抖音真实 API")
ALLOWED_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5175", "http://127.0.0.1:5175",
]
PUBLIC_API = {"/api/health", "/api/auth/status", "/api/auth/bootstrap", "/api/auth/login"}


def required_role(path: str, method: str) -> str:
    if path.startswith("/api/auth/users"):
        return "admin"
    if path == "/api/rules" and method == "PUT":
        return "admin"
    if path.startswith("/api/data-sources") and method != "GET":
        return "admin"
    if path.startswith("/api/integrations/douyin") and method != "GET":
        return "admin"
    if path == "/api/auth/logout":
        return "viewer"
    if method in {"POST", "PUT", "PATCH", "DELETE"} or path == "/api/recommendations/export":
        return "operator"
    return "viewer"


@app.middleware("http")
async def require_session(request: Request, call_next):
    path = request.url.path
    if path in {"/api/auth/bootstrap", "/api/auth/login"}:
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "不允许的请求来源"}, status_code=403)
    if request.method == "OPTIONS" or not path.startswith("/api/") or path in PUBLIC_API:
        return await call_next(request)
    session = auth_store.session(request.cookies.get(COOKIE_NAME))
    if not session:
        return JSONResponse({"detail": "请先登录"}, status_code=401)
    if ROLE_LEVEL[session["role"]] < ROLE_LEVEL[required_role(path, request.method)]:
        return JSONResponse({"detail": "当前角色没有此操作权限"}, status_code=403)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not csrf_valid(session, request.headers.get("x-csrf-token")):
        return JSONResponse({"detail": "CSRF 校验失败"}, status_code=403)
    request.state.user = session
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/auth/status")
def auth_status() -> dict:
    return {"data": {"initialized": auth_store.initialized(), "mode": settings.app_env}}


@app.post("/api/auth/bootstrap")
def bootstrap_admin(payload: LoginRequest, request: Request, response: Response) -> dict:
    if settings.app_env != "demo" or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="仅本地 Demo 允许首次初始化")
    try:
        auth_store.bootstrap(payload.username, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    token, user = auth_store.login(payload.username, payload.password, request.client.host)
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_TTL_SECONDS, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/api")
    return {"data": user}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    try:
        result = auth_store.login(payload.username, payload.password, request.client.host)
    except PermissionError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token, user = result
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_TTL_SECONDS, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/api")
    return {"data": user}


@app.get("/api/auth/me")
def current_user(request: Request) -> dict:
    return {"data": request.state.user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    auth_store.logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/api")
    return {"data": {"logged_out": True}}


@app.get("/api/auth/users")
def list_users() -> dict:
    return {"data": auth_store.list_users()}


@app.post("/api/auth/users")
def create_user(payload: UserCreateRequest) -> dict:
    try:
        return {"data": auth_store.create_user(payload.username, payload.password, payload.role)}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "mode": "demo", "llm_provider": settings.llm_provider, "models": runtime_models(), "real_douyin_api": False}


@app.get("/api/data-sources")
def list_data_sources() -> dict:
    return {"data": source_service.list_sources(), "meta": {"demo": True, "real_api": False}}


@app.post("/api/data-sources/{resource}/connect")
def connect_mock_source(resource: str) -> dict:
    try:
        return {"data": source_service.connect(resource), "meta": {"demo": True, "real_api": False}}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="未知数据源") from error


@app.post("/api/data-sources/{resource}/sync")
def sync_mock_source(resource: str) -> dict:
    try:
        return {"data": source_service.sync(resource), "meta": {"demo": True, "real_api": False}}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="未知数据源") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/integrations/douyin/status")
def douyin_integration_status() -> dict:
    return {"data": {
        "state": "pending_approval", "enabled": False, "outbound_requests": False,
        "message": "当前为离线 Demo。需完成官方应用和账号授权、逐项确认商品及热点接口权限后，才可部署正式适配器。",
        "resources": [
            {"resource": "products", "label": "精选联盟商品", "status": "pending_approval"},
            {"resource": "hotspots", "label": "热点趋势", "status": "pending_approval"},
        ],
        "prerequisites": ["官方应用及主体资质", "授权账号与对应权限", "商品和热点分别确认获批接口", "服务端安全保存凭证与审计", "生产适配器的字段映射和限流验收"],
    }}


@app.post("/api/integrations/douyin/authorize")
def begin_douyin_authorization() -> dict:
    raise HTTPException(status_code=409, detail="本地 Demo 禁止真实授权；请先完成官方资质及接口权限审批，生产环境部署专用授权适配器")


@app.post("/api/integrations/douyin/sync")
def sync_douyin_integration() -> dict:
    raise HTTPException(status_code=409, detail="本地 Demo 禁止真实 API 请求；正式同步需经官方授权和生产适配器验收")


@app.get("/api/models")
def models() -> dict:
    """Expose safe runtime model metadata; credentials never leave the server."""
    return {"data": runtime_models(), "meta": {"demo": True, "credentials_exposed": False}}


@app.get("/api/products")
def products(category: str | None = None, limit: int = Query(50, ge=1, le=200)) -> dict:
    rows = load_products()
    if category:
        rows = [row for row in rows if row["category"] == category]
    return {"data": rows[:limit], "meta": {"total": len(rows)}}


@app.get("/api/products/{product_id}")
def product_detail(product_id: str) -> dict:
    row = find_product(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"data": row}


@app.get("/api/data-quality")
def data_quality() -> dict:
    return {"data": service.data_quality(), "meta": {"demo": True}}


@app.get("/api/hotspots")
def hotspots() -> dict:
    rows = sorted(load_hotspots(), key=lambda row: row["heat_value"], reverse=True)
    return {"data": rows, "meta": {"total": len(rows)}}


@app.get("/api/hotspots/trends")
def hotspot_trends(days: int = Query(7, ge=1, le=30), category: str | None = None) -> dict:
    return {"data": service.hotspot_trends(days=days, category=category), "meta": {"demo": True, "real_api": False}}


@app.get("/api/hotspots/{hotspot_id}")
def hotspot_detail(hotspot_id: str) -> dict:
    row = find_hotspot(hotspot_id)
    if not row:
        raise HTTPException(status_code=404, detail="热点不存在")
    return {"data": row}


@app.get("/api/rules")
def get_rules() -> dict:
    return {"data": service.rules.model_dump()}


@app.put("/api/rules")
def update_rules(rules: RuleConfig) -> dict:
    service.rules = rules
    return {"data": rules.model_dump(), "message": "规则已更新，下一次推理生效"}


@app.post("/api/recommendations")
def recommendations(request: RecommendRequest) -> dict:
    try:
        result = service.recommend(request.hotspot_id, request.rules, request.limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"data": result, "meta": {"demo": True, "real_api": False}}


@app.post("/api/content-drafts")
def content_drafts(request: ContentDraftRequest) -> dict:
    try:
        result = service.create_content_draft(request.product_id, request.hotspot_id, request.recommendation_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"data": result, "meta": {"demo": True, "real_api": False}}


@app.get("/api/recommendations/export")
def export_recommendations(hotspot_id: str | None = None) -> StreamingResponse:
    result = service.recommend(hotspot_id, None, 50)
    stream = io.StringIO()
    columns = ["product_id", "title", "category", "price", "commission_rate", "final_score", "semantic_score", "multimodal_score", "content_topic", "match_reason"]
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(result["recommendations"])
    stream.seek(0)
    return StreamingResponse(iter([stream.getvalue().encode("utf-8-sig")]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=recommendations.csv"})


@app.post("/api/feedback")
def feedback(request: FeedbackRequest) -> dict:
    try:
        return {"data": service.add_feedback(request.model_dump())}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/feedback/summary")
def feedback_summary(product_id: str | None = None, hotspot_id: str | None = None) -> dict:
    return {"data": service.feedback_summary(product_id, hotspot_id), "meta": {"demo": True}}


@app.get("/api/feedback/records")
def feedback_records(product_id: str | None = None, hotspot_id: str | None = None, limit: int = Query(100, ge=1, le=500)) -> dict:
    rows = service.feedback_records(product_id, hotspot_id)
    return {"data": rows[:limit], "meta": {"total": len(rows)}}


@app.get("/api/feedback/trends")
def feedback_trends(product_id: str | None = None, hotspot_id: str | None = None) -> dict:
    return {"data": service.feedback_trends(product_id, hotspot_id), "meta": {"demo": True}}


@app.get("/api/loop/status")
def loop_status() -> dict:
    return {"data": service.loop_status(), "meta": {"demo": True, "training": "not_run"}}


@app.get("/api/loop/snapshots")
def loop_snapshots() -> dict:
    return {"data": service.list_training_snapshots(), "meta": {"demo": True, "simulation": True}}


@app.post("/api/loop/snapshots")
def create_loop_snapshot(request: SnapshotRequest | None = None) -> dict:
    snapshot = service.create_training_snapshot(request.note if request else None)
    return {"data": snapshot, "meta": {"demo": True, "simulation": True}}
