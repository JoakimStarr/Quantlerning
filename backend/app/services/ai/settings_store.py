"""AI 模型设置存储：读写 backend/data/ai_settings.json。

优先级设计：
- JSON 文件中显式配置的字段优先；
- 未配置的字段回退到 backend/.env 的默认值（settings.opencodezen_*）。

这样用户通过设置页保存的自定义配置生效，同时 .env 里已有的 key 仍作为兜底。
API key 只在后端保存；向浏览器返回时打码（masked），避免回显完整 key。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from app.core.config import settings

# backend/data/ai_settings.json
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"  # backend/data
SETTINGS_FILE = DATA_DIR / "ai_settings.json"

_lock = threading.Lock()

# 默认值（来自 .env，与 settings.opencodezen_* 一致）
DEFAULTS = {
    "base_url": settings.opencodezen_base_url,
    "api_key": settings.opencodezen_api_key,
    "model": settings.opencodezen_model,
    "max_tokens": settings.opencodezen_max_tokens,
}

# 前端可写字段
_EDITABLE = ("base_url", "api_key", "model", "max_tokens")


def _load() -> dict:
    """读取 JSON；文件不存在或损坏时返回空 dict。"""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def get_effective_config() -> dict:
    """返回生效的完整 AI 配置（JSON 覆盖 + .env 兜底）。"""
    with _lock:
        saved = _load()
    cfg = dict(DEFAULTS)
    for k in _EDITABLE:
        if k in saved and saved[k] not in (None, ""):
            cfg[k] = saved[k]
    # 类型安全
    try:
        cfg["max_tokens"] = int(cfg["max_tokens"] or 1024)
    except (TypeError, ValueError):
        cfg["max_tokens"] = 1024
    return cfg


def save_config(payload: dict) -> dict:
    """保存前端提交的配置（只接受白名单字段）。

    api_key 语义（避免误删已保存 key）：
    - 未提供（字段缺失/None）→ 保留原值
    - 空字符串 "" → 显式清除，回退到 .env
    - 非空 → 更新
    其余字段：空字符串 → 删除该字段，回退到 .env 默认。
    """
    with _lock:
        saved = _load()
        for k in _EDITABLE:
            if k not in payload:
                continue
            v = payload.get(k)
            if isinstance(v, str):
                v = v.strip()
            if k == "api_key":
                if v is None or v == "":
                    # 未提供 → 保留；显式空串 → 清除（与保留区分）
                    if v is None:
                        continue
                    saved.pop("api_key", None)
                else:
                    saved["api_key"] = v
                continue
            if v in (None, ""):
                saved.pop(k, None)
            else:
                saved[k] = v
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return get_effective_config()


def mask_key(key: str) -> str:
    """打码 API key：保留前 6 后 4，中间用 ***；空则返回空串。"""
    key = key or ""
    if len(key) <= 12:
        return "***" if key else ""
    return f"{key[:6]}***{key[-4:]}"


def public_config() -> dict:
    """返回给前端展示的配置（api_key 打码），并附带是否已配置标记。"""
    cfg = get_effective_config()
    return {
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "max_tokens": cfg["max_tokens"],
        "api_key_masked": mask_key(cfg["api_key"]),
        "configured": bool(cfg["api_key"]),
    }
