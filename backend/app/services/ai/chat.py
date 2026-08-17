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


class AIRateLimitError(AIProviderError):
    """触发提供商限流（HTTP 429）。上层据此切换备用模型。"""


# 429 限流错误 → 友好中文提示（提供商会返回原文 JSON，直接抛给前端体验差）
_RATE_LIMIT_HINTS = (
    "429",
    "rate limit",
    "rate_limit",
    "FreeUsageLimitError",
    "too many requests",
    "UsageLimit",
)
_RATE_LIMIT_MSG = "请求太频繁，触发了 AI 服务限流。请稍等 1~2 分钟再试。"


def is_rate_limit_error(message: str) -> bool:
    """判断错误原文是否属于限流（429）。"""
    low = (message or "").lower()
    return any(k in low for k in _RATE_LIMIT_HINTS)


def friendly_ai_error(message: str) -> str:
    """把 AI 提供商返回的错误原文转成面向用户的中文提示（仅限已知可识别错误）。"""
    if not message:
        return "AI 服务请求失败，请稍后重试"
    if is_rate_limit_error(message):
        return _RATE_LIMIT_MSG
    return message


def _find_lesson(lesson_id: str) -> dict | None:
    for phase in COURSES:
        for lesson in phase["lessons"]:
            if lesson["id"] == lesson_id:
                return lesson
    return None


def build_messages(
    lesson_id: str, section_index: int, history: list[dict], deep: bool = False
) -> list[dict]:
    """组装请求消息：system（课程+当前小节上下文）+ 最近几轮历史。

    deep=True 时启用「深度思考」：system 提示词要求先拆解问题、考虑常见误区，
    并放宽字数限制（配合 stream_chat 的 max_tokens 翻倍）。
    """
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
    if deep:
        system += (
            "\n\n本次提问开启「深度思考」模式：请先拆解问题、考虑常见的理解误区与不同解释，"
            "再给出结构化结论；可以分点展示推理过程，回答可以更详细、更深入，"
            "不受上述 300 字限制，但仍需条理清晰、不重复废话。"
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


def build_judge_followup_messages(
    lesson_id: str, section_index: int, question: str, answer: str, feedback: str, history: list[dict]
) -> list[dict]:
    """批改后追问：结合题目 + 学生答案 + 上轮批改反馈，回答学生对批改的疑问。"""
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
        "你是 Quantlerning 量化学习网站的 AI 辅导老师，用中文继续辅导学生。\n"
        f"课程：《{lesson['title']}》\n"
        f"当前小节：{section.get('title', '')}\n\n"
        f"本节课程内容（节选）：\n{body}\n\n"
        f"刚批改过的题目：\n{question}\n\n"
        f"学生的作答：\n{answer or '（未作答）'}\n\n"
        f"AI 给出的批改反馈：\n{feedback}\n\n"
        "学生针对刚才的批改继续追问，请结合本节知识解答其疑问：讲清思路、可举具体数字例子；"
        "不要编造数字或数据；数学公式必须用行内 LaTeX 单个美元符书写"
        "（如 $E[X]=\\sum_i x_i P(X=x_i)$），禁止用 Unicode 写公式；回答尽量控制在 300 字以内。"
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(history[-_HISTORY_LIMIT:])
    return messages


def build_gen_exercise_messages(
    lesson_id: str, section_index: int, question: str, answer: str, feedback: str
) -> list[dict]:
    """生成变式练习题：依据原题与学生作答表现，出同知识点、相近难度的变式题。"""
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
        "你是 Quantlerning 量化学习网站的出题老师，用中文为学生生成一道变式应用题。\n"
        f"课程：《{lesson['title']}》\n"
        f"当前小节：{section.get('title', '')}\n\n"
        f"本节课程内容（节选）：\n{body}\n\n"
        f"学生刚做过的原题：\n{question}\n\n"
        f"学生的作答：\n{answer or '（未作答）'}\n\n"
        f"AI 对该作答的批改：\n{feedback}\n\n"
        "请生成 1 道与本题考察同一知识点、难度相近的变式应用题。\n"
        "输出格式：先给题目（Markdown，数字要合理且可手算/简单公式验证），"
        "再单独一行写 `---`，随后给出完整参考答案与解题过程。\n"
        "要求：公式用行内 LaTeX 单个美元符；题目 200 字以内，参考答案 300 字以内；不编造无法计算的数字。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "请生成变式练习题。"},
    ]


def build_plan_messages(progress_summary: str) -> list[dict]:
    """学习路径规划：基于前端汇总的进度数据，给出复习重点与下一步建议。"""
    system = (
        "你是 Quantlerning 量化学习网站的学习规划导师，用中文给出一份个性化学习建议。\n"
        "基于学生当前学习进度数据，按 Markdown 输出：\n"
        "1. **掌握情况**：概括进度与强弱项；\n"
        "2. **建议复习**：点名 1-3 门最值得回看的课并说明原因；\n"
        "3. **下一步**：推荐接下来的学习重点与顺序。\n"
        "要求：只依据给出的数据，不编造；400 字以内；若数据显示是新手，给出入门建议。"
    )
    user_content = f"学生的学习进度数据：\n{progress_summary or '（暂无进度，属于刚入门阶段）'}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


async def _stream_once(
    messages: list[dict], cfg: dict, deep: bool = False
) -> AsyncGenerator[str, None]:
    """用给定配置发起一次流式调用，逐段 yield 回答文本。

    429 限流抛 AIRateLimitError（供上层切换备用模型）；其他非 200 抛 AIProviderError。
    deep=True 时 max_tokens 翻倍（深度思考需要更多输出空间），上限 4096。
    """
    if not cfg.get("api_key"):
        raise AINotConfiguredError(
            "AI API key 未配置。请在「设置」页填写，或 backend/.env 中填写 OPENCODEZEN_API_KEY。"
        )

    base_url = cfg["base_url"].rstrip("/") + "/"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    max_tokens = int(cfg.get("max_tokens") or 1024)
    if deep:
        max_tokens = min(max_tokens * 2, 4096)
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "temperature": float(cfg.get("temperature") or 0.4),
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(trust_env=False, timeout=60) as client:
            async with client.stream(
                "POST", f"{base_url}chat/completions", headers=headers, json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode("utf-8", errors="replace")
                    logger.warning("AI provider 返回 %s: %s", resp.status_code, body[:300])
                    msg = f"HTTP {resp.status_code}: {body[:200]}"
                    if resp.status_code == 429 or is_rate_limit_error(msg):
                        raise AIRateLimitError(friendly_ai_error(msg))
                    raise AIProviderError(friendly_ai_error(msg))
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


async def stream_chat(
    messages: list[dict], model: str | None = None, deep: bool = False
) -> AsyncGenerator[str, None]:
    """流式调用 LLM：先走主配置，限流(429)时自动切换备用模型。

    model 非空时覆盖本次使用的模型（如用户在面板手动选择）；deep=True 启用深度思考。
    备用模型未配置时保持原行为（限流错误透传给前端）。
    """
    from app.services.ai.settings_store import get_effective_config, get_fallback_config

    cfg = get_effective_config()
    if model:
        cfg["model"] = model
    try:
        async for delta in _stream_once(messages, cfg, deep=deep):
            yield delta
        return
    except AIRateLimitError:
        fb = get_fallback_config()
        if not fb:
            raise
        logger.info("主模型限流，切换备用模型 %s", fb.get("model"))
        async for delta in _stream_once(messages, fb, deep=deep):
            yield delta
