"""设置路由：AI 配置（provider 管理 + 全局参数）+ 模型列表 + 测试连接。

配置存后端 JSON（backend/data/ai_settings.json），api key 不回传完整值（打码）。

provider 管理：
- GET/PUT /settings/ai          全局参数（生成参数 + 联网搜索）
- POST   /settings/ai/providers                 新增自定义 provider
- PUT    /settings/ai/providers/{id}            更新（内置 id → 保存覆盖）
- DELETE /settings/ai/providers/{id}            删除自定义 / 重置内置
- POST   /settings/ai/providers/{id}/activate   设为当前
- POST   /settings/ai/providers/{id}/test       用存储配置测连接
- GET/POST /settings/ai/models                  模型列表（当前/表单）
- POST   /settings/ai/test                      表单式测连接（保存前预览）
"""
import json

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.ai import settings_store as store
from ..services.ai.chat import AIProviderError, friendly_ai_error

router = APIRouter(prefix="/settings", tags=["settings"])


class GlobalSettingsPayload(BaseModel):
    """全局参数：生成参数 + 联网搜索（provider 走独立端点）。"""
    max_tokens: int | None = Field(None, ge=16, le=8192)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    # 联网搜索（可选，Tavily key；None=保留原值，""=清除）
    web_search_key: str | None = Field(None, max_length=500)


class ProviderPayload(BaseModel):
    """provider 条目字段。api_key: None=保留原值、""=清除、非空=更新。"""
    name: str = Field("", max_length=100)
    base_url: str = Field("", max_length=300)
    model: str = Field("", max_length=200)
    api_key: str | None = Field(None, max_length=500)


class AITestPayload(BaseModel):
    """按表单提交的配置拉模型 / 测连接（保存前预览；未填项回退已保存/环境配置）。"""
    base_url: str = Field("", max_length=300)
    api_key: str = Field("", max_length=500)
    model: str = Field("", max_length=200)
    max_tokens: int | None = Field(None, ge=16, le=8192)
    temperature: float | None = Field(None, ge=0.0, le=2.0)


async def _fetch_models(base_url: str, api_key: str) -> list[str]:
    """调用 OpenAI 兼容的 GET {base_url}/models 拉取模型 id 列表。

    非 200 抛 AIProviderError；连接失败抛 httpx.HTTPError；JSON 非法抛 JSONDecodeError。
    """
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise AIProviderError(
                friendly_ai_error(f"HTTP {resp.status_code}: {resp.text[:200]}")
            )
        data = resp.json()
    return [m.get("id") for m in data.get("data") or [] if m.get("id")]


async def _test_connection(cfg: dict) -> dict:
    """用完整请求配置做一次非流式调用，返回 {"ok", "message", "reply"?}。"""
    if not cfg.get("api_key"):
        return {"ok": False, "message": "未配置 API key：请先填写"}
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": "你好，请只回复两个字：正常"}],
        "max_tokens": int(cfg.get("max_tokens") or 64),
        "stream": False,
        "temperature": float(
            cfg.get("temperature") if cfg.get("temperature") is not None else 0.2
        ),
    }
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                detail = resp.text[:200]
                return {
                    "ok": False,
                    "message": friendly_ai_error(f"HTTP {resp.status_code}: {detail}"),
                }
            data = resp.json()
        reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "message": "连接成功", "reply": reply}
    except httpx.HTTPError as e:
        raise AIProviderError(f"AI 服务连接失败: {e.__class__.__name__}: {e}") from e
    except json.JSONDecodeError:
        return {"ok": False, "message": "响应不是合法 JSON（可能 base_url 不对）"}


@router.get("/ai")
async def get_ai_settings():
    """返回完整 AI 配置：provider 列表（打码）+ 当前 provider + 全局参数。"""
    return store.public_config()


@router.put("/ai")
async def update_ai_settings(payload: GlobalSettingsPayload):
    """保存全局参数（生成参数 + 联网搜索）；返回保存后的配置。"""
    store.save_global_config(payload.model_dump())
    return store.public_config()


@router.get("/ai/models")
async def list_ai_models():
    """列出当前 provider 可用的模型（GET {base_url}/models）。

    提供商 models 接口不可用/失败时，回退为已配置模型，保证前端模型下拉总有可选值。
    返回 {"models": [...], "current": str}。
    """
    cfg = store.get_effective_config()
    configured: list[str] = []
    if cfg.get("model"):
        configured.append(cfg["model"])

    models: list[str] = []
    if cfg.get("api_key"):
        try:
            models = await _fetch_models(cfg["base_url"], cfg["api_key"])
        except (AIProviderError, httpx.HTTPError, json.JSONDecodeError):
            models = []

    if models:
        # 提供商列表成功：确保已配置模型也在列表里（缺失则补在最前）
        for m in reversed(configured):
            if m not in models:
                models.insert(0, m)
    else:
        models = configured
    return {"models": models, "current": cfg.get("model", "")}


@router.post("/ai/models")
async def fetch_ai_models(payload: AITestPayload):
    """按表单提交的 base_url/api_key 拉取模型列表（未填项回退已保存/环境配置）。

    供设置页「获取模型」按钮使用：保存前即可预览当前输入对应的可用模型。
    返回 {"models": [...], "current": str}；失败返回 {"models": [], "current": "", "error": msg}。
    """
    base = (payload.base_url or "").strip()
    key = (payload.api_key or "").strip()
    model = (payload.model or "").strip()
    if not base or not key:
        eff = store.get_effective_config()
        base = base or eff["base_url"]
        key = key or eff.get("api_key", "")
        model = model or eff["model"]
    if not key:
        return {"models": [], "current": model, "error": "未配置 API key"}

    try:
        models = await _fetch_models(base, key)
    except AIProviderError as e:
        return {"models": [], "current": model, "error": str(e)}
    except httpx.HTTPError as e:
        return {"models": [], "current": model, "error": f"AI 服务连接失败: {e.__class__.__name__}"}
    except json.JSONDecodeError:
        return {"models": [], "current": model, "error": "响应不是合法 JSON（可能 base_url 不对）"}

    # 当前输入模型若不在列表（如刚发布/别名），补在最前保证可选中
    if model and model not in models:
        models.insert(0, model)
    return {"models": models, "current": model}


@router.post("/ai/providers")
async def create_provider(payload: ProviderPayload):
    """新增自定义 provider；返回打码后的条目。"""
    try:
        return store.create_provider(payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/ai/providers/{provider_id}")
async def update_provider(provider_id: str, payload: ProviderPayload):
    """更新 provider（内置 id → 写入覆盖）；返回打码后的条目。

    exclude_unset：未提交的字段保留原值（Pydantic 默认会把缺省字段填成空串）。
    """
    try:
        return store.update_provider(
            provider_id, payload.model_dump(exclude_unset=True)
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/ai/providers/{provider_id}")
async def delete_provider(provider_id: str):
    """删除自定义 provider / 重置内置 provider；返回新的 active_provider_id。"""
    return {"active_provider_id": store.delete_provider(provider_id)}


@router.post("/ai/providers/{provider_id}/activate")
async def activate_provider(provider_id: str):
    """设为当前 provider。"""
    try:
        return {"active_provider_id": store.set_active_provider(provider_id)}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/ai/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    """用存储的 provider 配置做一次非流式调用，验证 base_url/model/api_key 可用。"""
    try:
        cfg = store.get_provider_config(provider_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return await _test_connection(cfg)


@router.post("/ai/test")
async def test_ai_settings(payload: AITestPayload):
    """用提交的配置做一次非流式调用，验证 base_url/model/api_key 可用（未保存）。

    返回 {"ok": bool, "message": str, "reply": str?}。
    """
    base = (payload.base_url or "").strip()
    key = (payload.api_key or "").strip()
    model = (payload.model or "").strip()
    max_tokens = payload.max_tokens
    temperature = payload.temperature
    if not base or not key or not model:
        eff = store.get_effective_config()
        base = base or eff["base_url"]
        key = key or eff.get("api_key", "")
        model = model or eff["model"]
        max_tokens = max_tokens or eff.get("max_tokens")
        temperature = temperature if temperature is not None else eff.get("temperature")
    return await _test_connection(
        {
            "base_url": base,
            "api_key": key,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    )
