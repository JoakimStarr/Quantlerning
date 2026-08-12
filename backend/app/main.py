"""Quantlerning FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, courses, data, exec as exec_api
from .api import settings as settings_api
from .core.config import settings
from .core.db import check_db_connection


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
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}
