"""设置路由：GET/PUT AI 配置 + POST 测试连接。

配置存后端 JSON（backend/data/ai_settings.json），api key 不回传完整值（打码）。
"""
import json

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.ai.chat import AIProviderError, friendly_ai_error
from ..services.ai.settings_store import public_config, save_config

router = APIRouter(prefix="/settings", tags=["settings"])


class AISettingsPayload(BaseModel):
    base_url: str = Field("", max_length=300)
    # None=未提供（保留原值）；""=显式清除；非空=更新
    api_key: str | None = Field(None, max_length=500)
    model: str = Field("", max_length=200)
    max_tokens: int | None = Field(None, ge=16, le=8192)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    # 备用模型（主模型限流时自动切换）
    fallback_base_url: str = Field("", max_length=300)
    fallback_api_key: str | None = Field(None, max_length=500)
    fallback_model: str = Field("", max_length=200)
    fallback_max_tokens: int | None = Field(None, ge=16, le=8192)


@router.get("/ai")
async def get_ai_settings():
    """返回当前 AI 配置（api_key 打码）。"""
    return public_config()


@router.get("/ai/models")
async def list_ai_models():
    """列出当前提供商可用的模型（GET {base_url}/models）。

    提供商 models 接口不可用/失败时，回退为主配置与备用配置中的模型（去重），
    保证前端模型下拉总有可选值。返回 {"models": [...], "current": str}。
    """
    from app.services.ai.settings_store import get_effective_config, get_fallback_config

    cfg = get_effective_config()
    configured: list[str] = []
    for m in (cfg.get("model"), (get_fallback_config() or {}).get("model")):
        if m and m not in configured:
            configured.append(m)

    models: list[str] = []
    if cfg.get("api_key"):
        url = cfg["base_url"].rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {cfg['api_key']}"}
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [
                        m.get("id") for m in data.get("data") or [] if m.get("id")
                    ]
        except (httpx.HTTPError, json.JSONDecodeError):
            models = []

    if models:
        # 提供商列表成功：确保已配置模型也在列表里（缺失则补在最前）
        for m in reversed(configured):
            if m not in models:
                models.insert(0, m)
    else:
        models = configured
    return {"models": models, "current": cfg.get("model", "")}


@router.put("/ai")
async def update_ai_settings(payload: AISettingsPayload):
    """保存 AI 配置；返回保存后的生效配置（api_key 打码）。"""
    save_config(payload.model_dump())
    return public_config()


@router.post("/ai/test")
async def test_ai_settings(payload: AISettingsPayload):
    """用提交的配置做一次非流式调用，验证 base_url/model/api_key 可用。

    返回 {"ok": bool, "message": str, "reply": str?}。
    """
    # 用提交的配置（未保存）临时测试；api_key 为空时回退到已保存/环境配置
    from app.services.ai.settings_store import get_effective_config

    base = (payload.base_url or "").strip()
    key = (payload.api_key or "").strip()
    model = (payload.model or "").strip()
    max_tokens = payload.max_tokens
    temperature = payload.temperature
    if not base or not key or not model:
        eff = get_effective_config()
        base = base or eff["base_url"]
        key = key or eff.get("api_key", "")
        model = model or eff["model"]
        max_tokens = max_tokens or eff.get("max_tokens")
        temperature = temperature if temperature is not None else eff.get("temperature")

    if not key:
        return {"ok": False, "message": "未配置 API key：请填写或先在设置页保存"}

    url = base.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "你好，请只回复两个字：正常"}],
        "max_tokens": int(max_tokens or 64),
        "stream": False,
        "temperature": temperature if temperature is not None else 0.2,
    }
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                detail = resp.text[:200]
                message = f"HTTP {resp.status_code}: {detail}"
                return {
                    "ok": False,
                    "message": friendly_ai_error(message),
                }
            data = resp.json()
        reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "message": "连接成功", "reply": reply}
    except httpx.HTTPError as e:
        raise AIProviderError(f"AI 服务连接失败: {e.__class__.__name__}: {e}") from e
    except json.JSONDecodeError:
        return {"ok": False, "message": "响应不是合法 JSON（可能 base_url 不对）"}
