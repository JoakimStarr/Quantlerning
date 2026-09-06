"""AI 追问服务：围绕当前课程知识点生成回答（OpenAI 兼容接口，流式）。

模型源：opencodezen（默认 https://opencode.ai/zen/v1，OpenAI 兼容）。
key 仅存后端 .env，不暴露前端。
"""
import json
import logging
import re
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


# 模型不可用（被服务商下架/改名等）错误特征词 → 可尝试切备用模型并引导换模型
_MODEL_ERROR_HINTS = (
    "not supported",
    "model not found",
    "model_not_found",
    "unknown model",
    "does not exist",
    "invalid model",
    "invalidmodelerror",
    "modelerror",
    "model does not",
)
_MODEL_GUIDE_MSG = "请在「设置」页点击「获取模型」重新选择可用模型后重试。"


def is_model_error(message: str) -> bool:
    """判断错误原文是否属于模型不可用（如 401 Model not supported）。"""
    low = (message or "").lower()
    return any(k in low for k in _MODEL_ERROR_HINTS)


def friendly_model_error(message: str) -> str:
    """模型不可用时的友好提示：保留原因 + 引导去设置页换模型。"""
    if not message:
        return f"当前模型不可用。{_MODEL_GUIDE_MSG}"
    return f"当前模型不可用：{message}。{_MODEL_GUIDE_MSG}"


def _find_lesson(lesson_id: str) -> dict | None:
    for phase in COURSES:
        for lesson in phase["lessons"]:
            if lesson["id"] == lesson_id:
                return lesson
    return None


# 跨小节检索：从用户问题提取检索词（拉丁词 + 中文 2-gram），匹配其他小节标题/正文
_STOPWORDS = {
    "什么", "为什么", "怎么", "如何", "这个", "那个", "一个", "一下", "有关", "关系",
    "区别", "是否", "不是", "没有", "就是", "可以", "应该", "咱们", "这里", "那里",
}


def _query_keywords(query: str) -> list[str]:
    """提取检索词：英文词 + 中文 2-gram，去掉常见停用词。"""
    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", query)]
    grams: list[str] = []
    for seg in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        if len(seg) <= 2:
            grams.append(seg)
        else:
            grams.extend(seg[i : i + 2] for i in range(len(seg) - 1))
    return [k for k in (words + grams) if k not in _STOPWORDS][:30]


def _match_sections(sections: list[dict], current_index: int, history: list[dict]) -> str:
    """轻量 RAG：用最后一条用户问题匹配其他小节，命中则返回可注入片段。"""
    query = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    if not query.strip():
        return ""
    keywords = _query_keywords(query)
    if not keywords:
        return ""
    scored: list[tuple[int, dict]] = []
    for i, s in enumerate(sections):
        if i == current_index:
            continue
        title = s.get("title") or ""
        body = s.get("body") or ""
        score = 0
        for kw in keywords:
            if kw in title:
                score += 3
            elif kw in body:
                score += 1
        if score >= 3:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    parts: list[str] = []
    for _, s in scored[:2]:
        snippet = (s.get("body") or "").strip().replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:300] + "…"
        parts.append(f"- 《{s.get('title', '')}》：{snippet}")
    return "\n".join(parts)


def build_messages(
    lesson_id: str,
    section_index: int,
    history: list[dict],
    deep: bool = False,
    guided: bool = False,
    context: str = "",
) -> list[dict]:
    """组装请求消息：system（课程+当前小节上下文）+ 最近几轮历史。

    deep=True 时启用「深度思考」：system 提示词要求先拆解问题、考虑常见误区，
    并放宽字数限制（配合 stream_chat 的 max_tokens 翻倍）。
    guided=True 时启用「引导式」教学：不直接给答案，反问+给思路（苏格拉底式）。
    context 非空时作为附加上下文注入（如代码沙箱的代码与运行结果，供 AI 分析）。
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
        "不要编造数字或数据；问题超出本小节但相关时可简要联系；"
        "回答一般控制在 500 字以内，复杂问题可适当展开，切勿为了凑字数反复重复。"
        "数学公式必须用行内 LaTeX 书写，用单个美元符包裹，例如 $E[X]=\\sum_i x_i P(X=x_i)$、"
        "$\\sigma=\\sqrt{\\frac{1}{n}\\sum (r_i-\\bar r)^2}$；"
        "块级公式用双美元符 $$...$$；"
        "公式与变量说明一律不要放进代码块（```）里，代码块只用于代码片段。"
        "禁止用 Unicode 字符写公式（如 σ²、√252、Pₜ 这类写法不要用）。"
    )
    # 跨小节：问题关键词命中其他小节时注入片段（轻量 RAG，回答「和前面 X 的关系」类问题）
    related = _match_sections(sections, section_index, history)
    if related:
        system += f"\n\n与本问题相关的其他小节内容（供参考）：\n{related}"
    if deep:
        system += (
        "\n\n本次提问开启「深度思考」模式：请先拆解问题、考虑常见的理解误区与不同解释，"
        "再给出结构化结论；可以分点展示推理过程，回答可以更详细、更深入，"
        "不受上述 500 字限制，但仍需条理清晰、不重复废话。"
        )
    if guided:
        system += (
            "\n\n本次提问开启「引导式」教学模式：不要直接给出完整答案。"
            "先用 1-2 个问题引导学生思考，指出关键概念与思路方向，必要时给一点小提示；"
            "等学生自己尝试后再确认或纠正，保持苏格拉底式启发。"
        )
    if context:
        system += (
            "\n\n以下是学生在代码沙箱中运行的代码与执行结果（供你结合分析，"
            "不要逐行复述整段代码）：\n"
            f"{context}"
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


_LETTERS = "ABCDEFGHIJ"


def build_quiz_explain_messages(
    lesson_id: str,
    section_index: int,
    question: str,
    options: list[str],
    correct_indexes: list[int],
    user_indexes: list[int],
) -> list[dict]:
    """选择题 AI 解析：结合课程小节上下文，讲清正确项为什么对、错误项错在哪。"""
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

    opt_lines = "\n".join(f"{_LETTERS[i]}. {options[i]}" for i in range(len(options)))
    correct = "、".join(_LETTERS[i] for i in correct_indexes) or "（题目未标记）"
    user_ans = "、".join(_LETTERS[i] for i in user_indexes) if user_indexes else "（未作答）"

    system = (
        "你是 Quantlerning 量化学习网站的测验讲解老师，用中文讲解选择题。\n"
        f"课程：《{lesson['title']}》\n"
        f"当前小节：{section.get('title', '')}\n\n"
        f"本节课程内容（节选）：\n{body}\n\n"
        "请结合本节知识讲清楚：① 正确选项为什么对；② 每个错误选项为什么错"
        "（若学生选错，重点指出他选的那个错在哪）。\n"
        "要求：数字不能编造；数学公式用行内 LaTeX 单个美元符；回答 250 字以内，用 Markdown 分条列出。"
    )
    user_content = (
        f"题目：\n{question}\n\n选项：\n{opt_lines}\n\n"
        f"正确答案：{correct}\n学生选择：{user_ans}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_quiz_variant_messages(
    lesson_id: str,
    section_index: int,
    question: str,
    options: list[str],
    correct_indexes: list[int],
    user_indexes: list[int],
) -> list[dict]:
    """生成变式选择题：基于原题与作答表现，出同知识点、相近难度的单选题。

    要求模型只输出 JSON（question/options/answer/explain），由上层解析并回填到前端测验卡。
    """
    lesson = _find_lesson(lesson_id)
    if lesson is None:
        raise ValueError(f"课程 {lesson_id} 不存在")
    content = get_content().get(lesson_id)
    if not content:
        raise ValueError(f"课程 {lesson_id} 没有内容")
    sections = content.get("sections") or []
    if not sections:
        raise ValueError(f"课程 {lesson_id} 没有内容")
    # 前端小节索引可能因内容 md 更新（缓存重建、sections 变少）而短暂越界：
    # 就近截断到边界，避免对用户硬报错（题目/选项已在请求里带全，上下文偏差可接受）
    if not 0 <= section_index < len(sections):
        logger.info(
            "quiz-variant 小节索引 %s 越界（共 %s 节），截断为 %s",
            section_index,
            len(sections),
            max(0, min(section_index, len(sections) - 1)),
        )
        section_index = max(0, min(section_index, len(sections) - 1))
    section = sections[section_index]

    body = (section.get("body") or "").strip()
    if len(body) > _MAX_BODY_CHARS:
        body = body[:_MAX_BODY_CHARS] + "\n…（内容已截断）"

    opt_lines = "\n".join(f"{_LETTERS[i]}. {options[i]}" for i in range(len(options)))
    correct = "、".join(_LETTERS[i] for i in correct_indexes) or "（题目未标记）"
    user_ans = "、".join(_LETTERS[i] for i in user_indexes) if user_indexes else "（未作答）"

    system = (
        "你是 Quantlerning 量化学习网站的出题老师，用中文生成一道变式选择题。\n"
        f"课程：《{lesson['title']}》\n"
        f"当前小节：{section.get('title', '')}\n\n"
        f"本节课程内容（节选）：\n{body}\n\n"
        "学生刚答错了一道随堂测验题。请生成 1 道与它考察同一知识点、难度相近的单选题变式题，"
        "并给出解析。\n"
        "只输出一个 JSON 对象，不要任何额外文字、Markdown 或代码围栏，字段：\n"
        '{"question": "题干（可用行内 LaTeX）", "options": ["选项1", "选项2", "选项3", "选项4"], '
        '"answer": [正确选项序号，1 起，单选题填一个数字], "explain": "解析，结合本节知识说明各选项对错"}。\n'
        "要求：选项 3-5 个；正确选项唯一；题干与选项中的公式用行内 LaTeX 单个美元符；"
        "数字要合理、可验证，不编造与课程无关的数据。"
    )
    user_content = (
        f"学生答错的原题：\n{question}\n\n选项：\n{opt_lines}\n\n"
        f"正确答案：{correct}\n学生选择：{user_ans}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def build_lesson_summary_messages(lesson_id: str) -> list[dict]:
    """章节小结：基于全课内容生成 3-5 条要点（内容过长截断控制 token 成本）。"""
    lesson = _find_lesson(lesson_id)
    if lesson is None:
        raise ValueError(f"课程 {lesson_id} 不存在")
    content = get_content().get(lesson_id)
    if not content:
        raise ValueError(f"课程 {lesson_id} 没有内容")
    sections = content.get("sections") or []

    parts = [f"# {lesson['title']}"]
    total = 0
    for s in sections:
        body = (s.get("body") or "").strip()
        if not body:
            continue
        title = s.get("title") or ""
        chunk = f"\n## {title}\n{body}" if title else f"\n{body}"
        total += len(chunk)
        if total > 4000:
            parts.append(f"\n## {title}\n…（内容过长，已截断）")
            break
        parts.append(chunk)
    lesson_text = "".join(parts)

    system = (
        "你是 Quantlerning 量化学习网站的小结导师，用中文为学习者生成一课小结。\n"
        "请基于课程全文，提炼 **3-5 条要点**，用 Markdown 无序列表输出；\n"
        "只依据课程内容，不编造数字或数据；每条要点一句话、可独立理解；"
        "涉及公式用行内 LaTeX 单个美元符；总长 250 字以内。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"课程全文：\n{lesson_text}"},
    ]


def build_review_messages(progress_summary: str) -> list[dict]:
    """错题弱项复习：基于学习进度与错题清单，给出薄弱点分析与复习建议。"""
    system = (
        "你是 Quantlerning 量化学习网站的错题回顾导师，用中文帮助学生复习薄弱点。\n"
        "基于学生的学习进度与错题清单，按 Markdown 输出：\n"
        "1. **薄弱点分析**：结合错题概括可能遗漏的知识点；\n"
        "2. **错题要点**：针对列出的错题，用一两句话点出关键概念或常见误区；\n"
        "3. **复习建议**：点名 1-3 个最值得重看的课程并说明原因。\n"
        "要求：只依据给出的数据，不编造；400 字以内；若没有错题，提示「暂无错题，继续保持」即可。"
    )
    user_content = f"学生的学习进度与错题数据：\n{progress_summary or '（暂无数据）'}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


async def _stream_once(
    messages: list[dict], cfg: dict, deep: bool = False, extra: dict | None = None
) -> AsyncGenerator[str, None]:
    """用给定配置发起一次流式调用，逐段 yield 回答文本。

    429 限流抛 AIRateLimitError（供上层切换备用模型）；其他非 200 抛 AIProviderError。
    deep=True 时 max_tokens 翻倍（深度思考需要更多输出空间），上限 8192。
    extra 为附加请求参数（如阿里云百炼的 {"enable_search": True}），原样并入请求体。
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
    max_tokens = int(cfg.get("max_tokens") or 4096)
    if deep:
        max_tokens = min(max_tokens * 2, 8192)
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": True,
        "temperature": float(cfg.get("temperature") or 0.4),
        "max_tokens": max_tokens,
    }
    if extra:
        payload.update(extra)

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
    messages: list[dict],
    model: str | None = None,
    deep: bool = False,
    extra: dict | None = None,
) -> AsyncGenerator[str, None]:
    """流式调用 LLM：先走当前 provider，异常时自动轮换其他已配置 key 的 provider。

    model 非空时覆盖本次使用的模型（如用户在面板手动选择）；deep=True 启用深度思考；
    extra 为附加请求参数（如阿里云百炼联网搜索 {"enable_search": True}），轮换到
    非 DashScope 的备用 provider 时自动丢弃（该参数仅阿里云/千问支持）。
    可降级异常：限流(429) 或 模型不可用（401 Model not supported 等）。
    全部 provider 失败时，模型错误给友好引导（去设置页换模型）。
    """
    from app.services.ai.settings_store import get_effective_config, get_rotation_providers, is_dashscope_base_url

    cfg = get_effective_config()
    if model:
        cfg["model"] = model
    rotations = get_rotation_providers()
    first_err: Exception | None = None
    try:
        async for delta in _stream_once(messages, cfg, deep=deep, extra=extra):
            yield delta
        return
    except (AIRateLimitError, AIProviderError) as e:
        if not (isinstance(e, AIRateLimitError) or is_model_error(str(e))):
            if is_model_error(str(e)):
                raise AIProviderError(friendly_model_error(str(e))) from e
            raise
        first_err = e
    # 当前 provider 限流/模型不可用 → 依次轮换其他已配置 key 的 provider
    last_err: Exception | None = None
    for p in rotations:
        alt = dict(cfg)
        alt.update(base_url=p["base_url"], model=p["model"], api_key=p["api_key"])
        # enable_search 等附加参数仅 DashScope 支持：备用源非阿里云/千问时丢弃，避免 400
        alt_extra = extra if is_dashscope_base_url(p["base_url"]) else None
        logger.info("主 provider 异常（%s），轮换 %s", first_err.__class__.__name__, p["model"])
        try:
            async for delta in _stream_once(messages, alt, deep=deep, extra=alt_extra):
                yield delta
            return
        except (AIRateLimitError, AIProviderError) as e2:
            last_err = e2
            if not (isinstance(e2, AIRateLimitError) or is_model_error(str(e2))):
                break
    # 全部失败：模型错误给友好引导
    err = last_err or first_err
    if isinstance(err, AIProviderError) and is_model_error(str(err)):
        raise AIProviderError(friendly_model_error(str(err))) from err
    if err:
        raise err
    return


async def complete_chat(
    messages: list[dict], model: str | None = None
) -> str:
    """非流式调用：收集完整回答文本。

    供结构化输出端点（如 /chat/quiz-variant）使用；复用 stream_chat 的
    provider 自动轮换逻辑，仅把流式增量拼成整段文本。
    """
    parts: list[str] = []
    async for delta in stream_chat(messages, model=model):
        parts.append(delta)
    return "".join(parts)
