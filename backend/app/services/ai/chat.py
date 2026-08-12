"""AI 追问服务：围绕当前课程知识点生成回答（OpenAI 兼容接口，流式）。

模型源：opencodezen（默认 https://opencode.ai/zen/v1，OpenAI 兼容）。
key 仅存后端 .env，不暴露前端。
"""
import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.services.content.courses import COURSES
from app.services.content.phase_loader import get_content

logger = logging.getLogger(__name__)

# 单节正文传给 LLM 的最大长度（token 成本控制）
_MAX_BODY_CHARS = 2000
# 多轮对话保留的历史条数
_HISTORY_LIMIT = 6


class AINotConfiguredError(Exception):
    """API key 未配置。"""


class AIProviderError(Exception):
    """调用 LLM 失败。"""


def _find_lesson(lesson_id: str) -> dict | None:
    for phase in COURSES:
        for lesson in phase["lessons"]:
            if lesson["id"] == lesson_id:
                return lesson
    return None


def build_messages(lesson_id: str, section_index: int, history: list[dict]) -> list[dict]:
    """组装请求消息：system（课程+当前小节上下文）+ 最近几轮历史。"""
    lesson = _find_lesson(lesson_id)
    if lesson is None:
        raise ValueError(f"课程 {lesson_id} 不存在")
    content = get_content().get(lesson_id)
    if not content:
        raise ValueError(f"课程 {lesson_id} 没有内容")
    sections = content.get("sections") or []
    if not 0 <= section_index < len(sections):
        raise ValueError(f"小节索引 {section_index} 越界（共 {len(sections)} 节）")
    section = sections[section_index]

    body = (section.get("body") or "").strip()
    if len(body) > _MAX_BODY_CHARS:
        body = body[:_MAX_BODY_CHARS] + "\n…（内容已截断）"

    system = (
        "你是 Quantlerning 量化学习网站的 AI 导师，用中文以循序渐进的方式讲解。\n"
        f"正在学习的课程：《{lesson['title']}》\n"
        f"当前小节：{section.get('title', '')}\n\n"
        f"本节课程内容（节选）：\n{body}\n\n"
        "请围绕该知识点回答用户问题。回答要准确、清晰，可配合具体例子说明；"
        "不要编造数字或数据；问题超出本小节但相关时可简要联系；回答尽量控制在 300 字以内。"
        "数学公式必须用行内 LaTeX 书写，用单个美元符包裹，例如 $E[X]=\\sum_i x_i P(X=x_i)$、"
        "$\\sigma=\\sqrt{\\frac{1}{n}\\sum (r_i-\\bar r)^2}$；"
        "禁止用 Unicode 字符写公式（如 σ²、√252、Pₜ 这类写法不要用）。"
    )
    messages = [{"role": "system", "content": system}]
    # 只保留最近若干轮历史，避免 token 膨胀
    messages.extend(history[-_HISTORY_LIMIT:])
    return messages


def build_judge_messages(
    lesson_id: str, section_index: int, question: str, answer: str
) -> list[dict]:
    """组装应用题批改消息：system（课程+小节上下文+批改要求）+ 题目 + 学生答案。"""
    lesson = _find_lesson(lesson_id)
    if lesson is None:
        raise ValueError(f"课程 {lesson_id} 不存在")
    content = get_content().get(lesson_id)
    if not content:
        raise ValueError(f"课程 {lesson_id} 没有内容")
    sections = content.get("sections") or []
    if not 0 <= section_index < len(sections):
        raise ValueError(f"小节索引 {section_index} 越界（共 {len(sections)} 节）")
    section = sections[section_index]

    body = (section.get("body") or "").strip()
    if len(body) > _MAX_BODY_CHARS:
        body = body[:_MAX_BODY_CHARS] + "\n…（内容已截断）"

    system = (
        "你是 Quantlerning 量化学习网站的应用题批改老师，用中文批改学生的计算/应用题。\n"
        f"课程：《{lesson['title']}》\n"
        f"当前小节：{section.get('title', '')}\n\n"
        f"本节课程内容（节选，供你判断题目依据）：\n{body}\n\n"
        "请严格按以下格式批改（用 Markdown）：\n"
        "1. **结论**：先给出「正确 / 基本正确 / 部分正确 / 错误」与百分制得分（0-100）。\n"
        "2. **点评**：用 2-4 条要点指出答对的点、错在哪、漏了什么。\n"
        "3. **参考答案**：给出完整且正确的解题过程。\n\n"
        "要求：严格依据本节课程知识判断，数字不能编造；"
        "数学公式必须用行内 LaTeX 书写，用单个美元符包裹，禁止用 Unicode 写公式（如 σ²、√252）；"
        "点评尽量控制在 200 字以内，参考答案控制在 300 字以内。"
    )
    user_content = f"题目：\n{question}\n\n学生答案：\n{answer or '（未作答）'}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


async def stream_chat(messages: list[dict]) -> AsyncGenerator[str, None]:
    """流式调用 LLM，逐段 yield 回答文本。配置优先取设置页（JSON），回退 .env。"""
    from app.services.ai.settings_store import get_effective_config

    cfg = get_effective_config()
    if not cfg.get("api_key"):
        raise AINotConfiguredError(
            "AI API key 未配置。请在「设置」页填写，或 backend/.env 中填写 OPENCODEZEN_API_KEY。"
        )

    base_url = cfg["base_url"].rstrip("/") + "/"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "temperature": 0.4,
        "max_tokens": int(cfg.get("max_tokens") or 1024),
    }

    try:
        async with httpx.AsyncClient(trust_env=False, timeout=60) as client:
            async with client.stream(
                "POST", f"{base_url}chat/completions", headers=headers, json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    logger.warning("AI provider 返回 %s: %s", resp.status_code, body[:300])
                    raise AIProviderError(f"AI 服务返回 {resp.status_code}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta
    except httpx.HTTPError as e:
        logger.warning("AI 调用网络错误: %s", e)
        raise AIProviderError(f"AI 服务连接失败: {e.__class__.__name__}") from e
