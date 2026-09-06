"""AI 模型设置存储：读写 backend/data/ai_settings.json。

数据模型（2026-08 多 provider 化）：
- providers: 用户保存的 provider 条目。内置三家（BUILTIN_PROVIDERS）默认不落盘，
  被编辑时写入同 id 覆盖条目；自定义 provider 使用 prov_ 前缀 id。
- active_provider_id: 当前生效的 provider。
- max_tokens / temperature: 全局生成参数（作用于当前 provider）。
- web_search_key: 联网搜索（Tavily）。

优先级：active provider 的 base_url/api_key/model 覆盖 .env 默认；
全局生成参数与 web_search_key 覆盖 .env；其余字段回退 backend/.env 默认值
（settings.opencodezen_*）。无任何用户配置时，生效配置 = .env 默认，行为与旧版一致。
API key 只在后端保存；向浏览器返回时打码（masked）。

自动轮换：主 provider 限流（429）或模型不可用时，chat 层按 get_rotation_providers()
依次尝试其他已配置 api key 的 provider。
"""
from __future__ import annotations

import json
import threading
import uuid
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

# 内置四家默认 provider（OpenAI 兼容接口）。OpenCodeZen 跟随 .env（保持零配置行为不变）。
BUILTIN_PROVIDERS = [
    {
        "id": "builtin_glm",
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4.7-flash",
    },
    {
        "id": "builtin_opencodezen",
        "name": "OpenCodeZen",
        "base_url": settings.opencodezen_base_url or "https://opencode.ai/zen/v1",
        "model": settings.opencodezen_model,
    },
    {
        "id": "builtin_siliconflow",
        "name": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
    },
    {
        "id": "builtin_dashscope",
        "name": "阿里云百炼（千问）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
]


def is_dashscope_base_url(base_url: str) -> bool:
    """是否为阿里云百炼（DashScope）接口：仅这类模型源支持内置联网搜索（enable_search）。

    覆盖国内 dashscope.aliyuncs.com 与海外 dashscope-intl.aliyuncs.com（自定义
    provider 填 DashScope 地址同样命中）。
    """
    return "dashscope" in (base_url or "").lower()

# 全局参数（顶层保存字段）
_GLOBAL_KEYS = ("max_tokens", "temperature", "web_search_key")


def _load() -> dict:
    """读取 JSON（须在持锁下调用）；文件不存在或损坏时返回空 dict；首次读取自动迁移旧格式。"""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return {}
    if "providers" not in saved:
        saved = _migrate_legacy(saved)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return saved


def _write(saved: dict) -> None:
    """写回 JSON（须在持锁下调用）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------- 旧格式迁移 ----------

def _migrate_legacy(saved: dict) -> dict:
    """把旧版「主配置 + 备用配置」迁移为 provider 列表。

    主配置 base_url 命中内置 → 生成同 id 覆盖条目；否则生成自定义条目。
    备用配置 key 未单独配置时沿用主 key（与旧版运行时行为一致）。
    max_tokens / temperature / web_search_key 保留顶层作为全局参数。
    """
    main_url = (saved.get("base_url") or "").strip()
    main_key = saved.get("api_key") or ""
    main_model = (saved.get("model") or "").strip()
    fb_url = (saved.get("fallback_base_url") or "").strip()
    fb_key = saved.get("fallback_api_key") or ""
    fb_model = (saved.get("fallback_model") or "").strip()

    providers: list[dict] = []
    active_id: str | None = None
    if main_url:
        entry, _ = _legacy_entry("主模型", main_url, main_model, main_key)
        providers.append(entry)
        active_id = entry["id"]
    if fb_url:
        entry, _ = _legacy_entry("备用模型", fb_url, fb_model, fb_key or main_key)
        providers.append(entry)
        active_id = active_id or entry["id"]

    saved["providers"] = providers
    saved["active_provider_id"] = active_id or BUILTIN_PROVIDERS[0]["id"]
    return saved


def _legacy_entry(name: str, base_url: str, model: str, api_key: str) -> tuple[dict, str | None]:
    """按 base_url 命中内置 → 生成同 id 覆盖条目；否则生成自定义条目。

    返回 (条目, 命中的内置 id 或 None)。
    """
    for b in BUILTIN_PROVIDERS:
        if b["base_url"].rstrip("/") == base_url.rstrip("/"):
            return {
                "id": b["id"],
                "name": b["name"],
                "base_url": base_url,
                "model": model or b["model"],
                **({"api_key": api_key} if api_key else {}),
            }, b["id"]
    entry: dict = {
        "id": "prov_legacy_" + uuid.uuid4().hex[:6],
        "name": name,
        "base_url": base_url,
    }
    if model:
        entry["model"] = model
    if api_key:
        entry["api_key"] = api_key
    return entry, None


# ---------- 读取 ----------

def get_providers() -> list[dict]:
    """合并后的 provider 列表：内置三家在前，自定义追加在后；同 id 覆盖内置。

    每个条目含 id/name/base_url/model/api_key/builtin。
    """
    with _lock:
        saved = _load()
        stored = {p["id"]: p for p in saved.get("providers") or []}
    merged: list[dict] = []
    for b in BUILTIN_PROVIDERS:
        item = dict(b)
        if b["id"] in stored:
            item.update(
                {k: v for k, v in stored[b["id"]].items() if v not in (None, "")}
            )
        item["builtin"] = True
        merged.append(item)
    for p in stored.values():
        if any(p["id"] == m["id"] for m in merged):
            continue
        item = dict(p)
        item.setdefault("base_url", "")
        item.setdefault("model", "")
        item["builtin"] = False
        merged.append(item)
    return merged


def get_active_provider_id() -> str | None:
    """当前生效 provider 的 id；未设置时取列表第一个。"""
    with _lock:
        saved = _load()
        active = saved.get("active_provider_id")
    if active:
        return active
    providers = get_providers()
    return providers[0]["id"] if providers else None


def get_active_provider() -> dict | None:
    """当前生效 provider 条目；active 失效时回退列表第一个；无列表返回 None。"""
    providers = get_providers()
    if not providers:
        return None
    active_id = get_active_provider_id()
    for p in providers:
        if p["id"] == active_id:
            return p
    return providers[0]


def get_provider_config(provider_id: str) -> dict:
    """返回指定 provider 的完整请求配置（含全局 max_tokens/temperature），供测试连接使用。"""
    providers = get_providers()
    p = next((x for x in providers if x["id"] == provider_id), None)
    if p is None:
        raise KeyError(f"provider 不存在: {provider_id}")
    with _lock:
        saved = _load()
    cfg = dict(DEFAULTS)
    for k in _GLOBAL_KEYS:
        if saved.get(k) not in (None, ""):
            cfg[k] = saved[k]
    for k in ("base_url", "api_key", "model"):
        if p.get(k):
            cfg[k] = p[k]
    return _normalize(cfg)


def get_effective_config() -> dict:
    """返回当前生效的完整 AI 配置（active provider + 全局参数 + .env 兜底）。"""
    prov = get_active_provider()
    with _lock:
        saved = _load()
    cfg = dict(DEFAULTS)
    for k in _GLOBAL_KEYS:
        if saved.get(k) not in (None, ""):
            cfg[k] = saved[k]
    if prov:
        for k in ("base_url", "api_key", "model"):
            if prov.get(k):
                cfg[k] = prov[k]
    return _normalize(cfg)


def get_rotation_providers() -> list[dict]:
    """当前 provider 之外、已配置 api_key 的 provider 配置列表（按列表顺序）。

    供 chat 层在主 provider 限流/模型不可用时自动轮换。
    """
    active_id = get_active_provider_id()
    return [
        {"base_url": p["base_url"], "model": p["model"], "api_key": p["api_key"]}
        for p in get_providers()
        if p["id"] != active_id and p.get("api_key")
    ]


# ---------- 写入 ----------

def save_global_config(payload: dict) -> dict:
    """保存全局参数（max_tokens / temperature / web_search_key）。

    web_search_key 语义：未提供 → 保留；空串 → 清除；非空 → 更新。
    """
    with _lock:
        saved = _load()
        if "max_tokens" in payload and payload["max_tokens"] is not None:
            saved["max_tokens"] = payload["max_tokens"]
        if "temperature" in payload and payload["temperature"] is not None:
            saved["temperature"] = payload["temperature"]
        if "web_search_key" in payload:
            v = payload["web_search_key"]
            if v is None:
                pass
            elif str(v).strip() == "":
                saved.pop("web_search_key", None)
            else:
                saved["web_search_key"] = str(v).strip()
        _write(saved)
    return get_effective_config()


def create_provider(payload: dict) -> dict:
    """新增自定义 provider；返回打码后的 provider（含 id/builtin 标记）。"""
    name = (payload.get("name") or "").strip()
    base_url = (payload.get("base_url") or "").strip()
    model = (payload.get("model") or "").strip()
    if not name or not base_url or not model:
        raise ValueError("name / base_url / model 均不能为空")
    entry: dict = {
        "id": "prov_" + uuid.uuid4().hex[:10],
        "name": name,
        "base_url": base_url,
        "model": model,
    }
    api_key = (payload.get("api_key") or "").strip()
    if api_key:
        entry["api_key"] = api_key
    with _lock:
        saved = _load()
        saved.setdefault("providers", []).append(entry)
        _write(saved)
    return _public_provider(entry, builtin=False)


def update_provider(provider_id: str, payload: dict) -> dict:
    """更新 provider。内置 id → 写入覆盖条目；自定义 → 修改条目。

    api_key 语义：未提供(None) → 保留；空串 → 清除；非空 → 更新。
    其余字段：空字符串 → 清除（内置覆盖条目清除后回退内置默认）。
    """
    with _lock:
        saved = _load()
        providers = saved.setdefault("providers", [])
        entry = next((p for p in providers if p["id"] == provider_id), None)
        builtin = next((b for b in BUILTIN_PROVIDERS if b["id"] == provider_id), None)
        if entry is None:
            if builtin is None:
                raise KeyError(f"provider 不存在: {provider_id}")
            entry = {
                "id": builtin["id"],
                "name": builtin["name"],
                "base_url": builtin["base_url"],
                "model": builtin["model"],
            }
            providers.append(entry)
        for field in ("name", "base_url", "model"):
            if field not in payload:
                continue
            v = payload[field]
            if v is None:
                continue
            v = str(v).strip()
            # 空串 = 未提交（partial update），保留原值；provider 必填字段不支持清除
            if v:
                entry[field] = v
        if "api_key" in payload:
            v = payload["api_key"]
            if v is None:
                pass
            elif str(v).strip() == "":
                entry.pop("api_key", None)
            else:
                entry["api_key"] = str(v).strip()
        _write(saved)
    merged = next(p for p in get_providers() if p["id"] == provider_id)
    return _public_provider(merged, builtin=bool(merged.get("builtin")))


def delete_provider(provider_id: str) -> str:
    """删除自定义 provider / 重置内置 provider 覆盖；返回新的 active_provider_id。

    删除的恰是当前 provider 时，active 自动回退到列表第一个。
    """
    with _lock:
        saved = _load()
        saved["providers"] = [p for p in saved.get("providers") or [] if p["id"] != provider_id]
        if saved.get("active_provider_id") == provider_id:
            saved.pop("active_provider_id", None)
        _write(saved)
    return get_active_provider_id() or ""


def set_active_provider(provider_id: str) -> str:
    """设为当前 provider；id 无效抛 KeyError。"""
    ids = {p["id"] for p in get_providers()}
    if provider_id not in ids:
        raise KeyError(f"provider 不存在: {provider_id}")
    with _lock:
        saved = _load()
        saved["active_provider_id"] = provider_id
        _write(saved)
    return provider_id


# ---------- 展示 ----------

def _public_provider(p: dict, builtin: bool) -> dict:
    """单个 provider 的打码展示形状（对缺字段容错）。"""
    return {
        "id": p["id"],
        "name": p.get("name", ""),
        "base_url": p.get("base_url", ""),
        "model": p.get("model", ""),
        "api_key_masked": mask_key(p.get("api_key", "")),
        "configured": bool(p.get("api_key")),
        "builtin": builtin,
    }


def public_config() -> dict:
    """返回给前端展示的完整配置（api_key 打码）。

    builtin_web_search：当前模型源是否为阿里云百炼（DashScope）——
    这类源支持模型内置联网搜索（enable_search），「联网」开关无需 Tavily key 即可用。
    """
    cfg = get_effective_config()
    return {
        "providers": [_public_provider(p, builtin=bool(p.get("builtin"))) for p in get_providers()],
        "active_provider_id": get_active_provider_id() or "",
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
        "web_search_key_masked": mask_key(cfg.get("web_search_key", "")),
        "web_search_configured": bool(cfg.get("web_search_key")),
        "builtin_web_search": is_dashscope_base_url(cfg.get("base_url", "")),
    }


def mask_key(key: str) -> str:
    """打码 API key：保留前 6 后 4，中间用 ***；空则返回空串。"""
    key = key or ""
    if len(key) <= 12:
        return "***" if key else ""
    return f"{key[:6]}***{key[-4:]}"


def _normalize(cfg: dict) -> dict:
    """类型安全归一化（max_tokens / temperature 钳制）。"""
    try:
        cfg["max_tokens"] = int(cfg["max_tokens"] or 4096)
    except (TypeError, ValueError):
        cfg["max_tokens"] = 4096
    try:
        cfg["temperature"] = float(cfg["temperature"] if cfg.get("temperature") is not None else 0.4)
    except (TypeError, ValueError):
        cfg["temperature"] = 0.4
    cfg["temperature"] = max(0.0, min(2.0, cfg["temperature"]))
    return cfg
