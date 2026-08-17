"""AI 模型设置存储：读写 backend/data/ai_settings.json。

优先级设计：
- JSON 文件中显式配置的字段优先；
- 未配置的字段回退到 backend/.env 的默认值（settings.opencodezen_*）。

这样用户通过设置页保存的自定义配置生效，同时 .env 里已有的 key 仍作为兜底。
API key 只在后端保存；向浏览器返回时打码（masked），避免回显完整 key。

支持主/备两套配置（fallback）：
- 主配置：base_url / api_key / model / max_tokens / temperature
- 备用配置（可选）：fallback_base_url / fallback_api_key / fallback_model / fallback_max_tokens
  主模型限流（429）时自动切换备用，避免 AI 追问/批改直接失败。
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
    "temperature": settings.opencodezen_temperature,
    # 联网搜索（可选，Tavily）
    "web_search_key": settings.tavily_api_key,
}

# 前端可写字段（主配置 + 备用配置 + 联网搜索）
_EDITABLE = (
    "base_url",
    "api_key",
    "model",
    "max_tokens",
    "temperature",
    "fallback_base_url",
    "fallback_api_key",
    "fallback_model",
    "fallback_max_tokens",
    "web_search_key",
)

# 备用配置字段（不含 temperature：备用复用主配置的温度）
_FALLBACK_KEYS = (
    "fallback_base_url",
    "fallback_api_key",
    "fallback_model",
    "fallback_max_tokens",
)


def _load() -> dict:
    """读取 JSON；文件不存在或损坏时返回空 dict。"""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _normalize(cfg: dict) -> dict:
    """类型安全归一化（max_tokens / temperature 钳制）。"""
    try:
        cfg["max_tokens"] = int(cfg["max_tokens"] or 1024)
    except (TypeError, ValueError):
        cfg["max_tokens"] = 1024
    try:
        cfg["temperature"] = float(cfg["temperature"] if cfg.get("temperature") is not None else 0.4)
    except (TypeError, ValueError):
        cfg["temperature"] = 0.4
    cfg["temperature"] = max(0.0, min(2.0, cfg["temperature"]))
    return cfg


def get_effective_config() -> dict:
    """返回生效的完整主 AI 配置（JSON 覆盖 + .env 兜底）。"""
    with _lock:
        saved = _load()
    cfg = dict(DEFAULTS)
    for k in _EDITABLE:
        if k in saved and saved[k] not in (None, ""):
            cfg[k] = saved[k]
    return _normalize(cfg)


def get_fallback_config() -> dict | None:
    """返回备用 AI 配置；未配置（缺 base_url 或 model）时返回 None。

    备用配置 base_url/model 只读取 JSON 保存的字段，不回退 .env（避免与主配置相同形成无效兜底）；
    api_key 允许回退到主配置的 key（同供应商换模型时只需填 base_url/model）。
    """
    with _lock:
        saved = _load()
    fb = {k.replace("fallback_", ""): saved[k] for k in _FALLBACK_KEYS if saved.get(k) not in (None, "")}
    if not fb.get("base_url") or not fb.get("model"):
        return None
    # 备用复用主配置的温度与 api key（api key 未单独配置时）
    main = get_effective_config()
    fb["temperature"] = main["temperature"]
    if not fb.get("api_key"):
        fb["api_key"] = main.get("api_key") or ""
    try:
        fb["max_tokens"] = int(fb.get("max_tokens") or main.get("max_tokens") or 1024)
    except (TypeError, ValueError):
        fb["max_tokens"] = 1024
    return fb


def save_config(payload: dict) -> dict:
    """保存前端提交的配置（只接受白名单字段）。

    api_key / fallback_api_key 语义（避免误删已保存 key）：
    - 未提供（字段缺失/None）→ 保留原值
    - 空字符串 "" → 显式清除，回退到 .env（或无备用）
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
            is_key = k in ("api_key", "fallback_api_key", "web_search_key")
            if is_key:
                if v is None or v == "":
                    # 未提供 → 保留；显式空串 → 清除（与保留区分）
                    if v is None:
                        continue
                    saved.pop(k, None)
                else:
                    saved[k] = v
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
    fb = get_fallback_config()
    # 备用是否单独配置了 key（回退到主 key 的不算「单独配置」）
    with _lock:
        saved = _load()
    fb_own_key = bool(saved.get("fallback_api_key"))
    return {
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
        "api_key_masked": mask_key(cfg["api_key"]),
        "configured": bool(cfg["api_key"]),
        "fallback_base_url": (fb or {}).get("base_url", ""),
        "fallback_model": (fb or {}).get("model", ""),
        "fallback_max_tokens": (fb or {}).get("max_tokens"),
        "fallback_api_key_masked": mask_key((fb or {}).get("api_key", "")) if fb_own_key else "",
        "fallback_configured": fb is not None,
        "web_search_key_masked": mask_key(cfg.get("web_search_key", "")),
        "web_search_configured": bool(cfg.get("web_search_key")),
    }
