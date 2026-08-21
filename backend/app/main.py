"""Quantlerning FastAPI 入口。"""
from contextlib import asynccontextmanager
from mimetypes import guess_type
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers

from .api import chat, courses, data, exec as exec_api
from .api import settings as settings_api
from .core.config import settings
from .core.db import check_db_connection

# 生产模式静态资源：frontend/dist（npm run build 产物）。不存在时跳过托管（纯 API 模式）
DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
HAS_DIST = (DIST_DIR / "index.html").exists()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时验证 DB 连接
    try:
        info = await check_db_connection()
        print(f"[Quantlerning] DB connected: {info}")
    except Exception as e:  # noqa: BLE001
        print(f"[Quantlerning] WARNING: DB connection failed: {e}")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS：开发环境允许前端 Vite 端口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip 压缩（对非 SSE 端点）：压缩 JSON/文本响应，显著减小穿透带宽。
# 注意：SSE（/api/v1/chat/* 流式回答）不能 gzip——压缩会缓冲整个流，破坏逐字实时输出。
from starlette.middleware.gzip import GZipMiddleware

_GZIP_EXCLUDE = ("/api/v1/chat", "/api/v1/exec")  # SSE 流式端点不压缩


class _GzipNoSSE:
    """GZip 中间件，但排除 SSE 路径：流式响应需要逐块实时到达，gzip 会缓冲破坏实时性。"""

    def __init__(self, app, minimum_size=500):
        self.app = app
        self.inner = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith(_GZIP_EXCLUDE):
            await self.app(scope, receive, send)
            return
        await self.inner(scope, receive, send)


app.add_middleware(_GzipNoSSE)


class _BrotliStatic:
    """brotli 预压缩静态分发：命中 /assets 且 Accept-Encoding: br 且有 .br 文件时，
    直接返回预压缩字节（不经过 GZip，避免二次压缩）。需要放在最外层（后 add 先执行）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not HAS_DIST:
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if not path.startswith("/assets/"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        if "br" not in headers.get("Accept-Encoding", ""):
            await self.app(scope, receive, send)
            return
        # 找同名 .br 文件（vite-plugin-compression 生成）
        rel = path[len("/assets/") :]
        br_file = DIST_DIR / "assets" / f"{rel}.br"
        if not br_file.is_file():
            await self.app(scope, receive, send)
            return
        body = br_file.read_bytes()
        ctype = guess_type(rel)[0] or "application/octet-stream"
        resp_headers = [
            (b"content-type", ctype.encode()),
            (b"content-encoding", b"br"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"public, max-age=31536000, immutable"),
            (b"vary", b"accept-encoding"),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": resp_headers})
        await send({"type": "http.response.body", "body": body})


# 注册顺序：后 add 先执行 → _BrotliStatic 在最外层，GZip 在其内，CORS 最内层
app.add_middleware(_BrotliStatic)

app.include_router(courses.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(settings_api.router, prefix="/api/v1")
app.include_router(exec_api.router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    """健康检查。"""
    try:
        db_info = await check_db_connection()
        db_status = "ok"
    except Exception:  # noqa: BLE001
        db_info = None
        db_status = "error"
    return {"status": "ok", "db": db_status, "tables": db_info}


@app.get("/")
async def root():
    # 生产模式（已构建 dist）：根路径直接返回首页
    if HAS_DIST:
        return FileResponse(DIST_DIR / "index.html")
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}


# ---- 生产模式静态托管（仅当 dist 已构建）----
if HAS_DIST:
    # 带 content hash 的构建产物：长缓存
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA fallback：/assets 与 /api 之外的路径都返回 index.html（history 路由）。"""
        # 图标等静态文件直接从 dist 根目录返回
        file = DIST_DIR / full_path
        if full_path and file.is_file() and file.resolve().is_relative_to(DIST_DIR.resolve()):
            return FileResponse(file)
        return FileResponse(DIST_DIR / "index.html")
