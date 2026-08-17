"""AI 追问路由：POST /api/v1/chat/stream（SSE 流式）。"""
import json
from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..services.ai.chat import (
    AINotConfiguredError,
    AIProviderError,
    build_gen_exercise_messages,
    build_judge_followup_messages,
    build_judge_messages,
    build_lesson_summary_messages,
    build_messages,
    build_plan_messages,
    build_quiz_explain_messages,
    build_quiz_variant_messages,
    build_review_messages,
    complete_chat,
    stream_chat,
)
from ..services.ai.web_search import (
    WebSearchError,
    WebSearchNotConfiguredError,
    build_search_context,
    web_search,
)

router = APIRouter(prefix="/chat", tags=["chat"])

_MAX_MSG_LEN = 2000  # 单条用户消息长度上限
_MAX_HISTORY = 20  # 前端可传历史条数上限


class ChatMessage(BaseModel):
    role: str  # 仅允许 user / assistant（system 由后端构造）
    content: str


class ChatRequest(BaseModel):
    lesson_id: str
    section_index: int = 0
    messages: list[ChatMessage] = Field(default_factory=list)
    # 面板可选：覆盖模型（空=用当前配置）；深度思考开关；联网搜索开关
    model: str | None = Field(None, max_length=200)
    deep: bool = False
    web_search: bool = False
    # 引导式教学开关；代码沙箱等附加上下文（注入 system，不走历史截断）
    guided: bool = False
    context: str | None = Field(None, max_length=6000)


class JudgeRequest(BaseModel):
    lesson_id: str
    section_index: int = 0
    question: str = Field(..., max_length=2000)
    answer: str = Field("", max_length=4000)


class JudgeFollowupRequest(BaseModel):
    lesson_id: str
    section_index: int = 0
    question: str = Field(..., max_length=2000)
    answer: str = Field("", max_length=4000)
    feedback: str = Field("", max_length=8000)
    messages: list[ChatMessage] = Field(default_factory=list)


class GenExerciseRequest(BaseModel):
    lesson_id: str
    section_index: int = 0
    question: str = Field(..., max_length=2000)
    answer: str = Field("", max_length=4000)
    feedback: str = Field("", max_length=8000)


class QuizVariantRequest(BaseModel):
    lesson_id: str
    section_index: int = 0
    question: str = Field(..., max_length=2000)
    options: list[str] = Field(default_factory=list)
    correct_indexes: list[int] = Field(default_factory=list)
    user_indexes: list[int] = Field(default_factory=list)


class PlanRequest(BaseModel):
    summary: str = Field("", max_length=8000)


class QuizExplainRequest(BaseModel):
    lesson_id: str
    section_index: int = 0
    question: str = Field(..., max_length=2000)
    options: list[str] = Field(default_factory=list)
    correct_indexes: list[int] = Field(default_factory=list)
    user_indexes: list[int] = Field(default_factory=list)


class LessonSummaryRequest(BaseModel):
    lesson_id: str


class ReviewRequest(BaseModel):
    summary: str = Field("", max_length=8000)


def _sse(event: str) -> str:
    """序列化 SSE data 事件。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _sse_stream(build: Callable[[], list[dict]]) -> StreamingResponse:
    """构造 SSE 响应：传入消息构造函数，统一处理错误事件（404 课程/未配置/服务错误）。"""
    async def gen():
        try:
            messages = build()
        except ValueError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
            return
        try:
            async for delta in stream_chat(messages):
                yield _sse({"delta": delta})
            yield _sse({"done": True})
        except AINotConfiguredError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
        except AIProviderError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
        except Exception:  # noqa: BLE001 兜底：避免未捕获异常直接中断 SSE 流
            yield _sse({"error": "服务内部错误，请稍后重试"})
            yield _sse({"done": True})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _clean_history(messages: list[ChatMessage]) -> list[dict]:
    """校验并清洗历史消息（角色与长度）。"""
    history = []
    for m in messages[-_MAX_HISTORY:]:
        if m.role not in ("user", "assistant"):
            continue
        content = m.content.strip()
        if content:
            history.append({"role": m.role, "content": content[:_MAX_MSG_LEN]})
    return history


@router.post("/stream")
async def chat_stream(payload: ChatRequest):
    """围绕当前课程小节追问，SSE 流式返回。

    事件：{"delta": str} 增量文本；{"done": true} 结束；{"error": str} 出错。
    """
    # 校验历史消息角色与长度
    history = []
    for m in payload.messages[-_MAX_HISTORY:]:
        if m.role not in ("user", "assistant"):
            return StreamingResponse(
                iter([_sse({"error": "历史消息角色非法"}), _sse({"done": True})]),
                media_type="text/event-stream",
            )
        content = m.content.strip()
        if content:
            history.append({"role": m.role, "content": content[:_MAX_MSG_LEN]})

    async def gen():
        sources: list[dict] = []
        try:
            messages = build_messages(
                payload.lesson_id,
                payload.section_index,
                history,
                deep=payload.deep,
                guided=payload.guided,
                context=payload.context or "",
            )
            # 联网搜索：用最后一条用户消息检索，结果作为 system 上下文注入（标注外部来源）
            if payload.web_search:
                from app.services.ai.settings_store import get_effective_config

                cfg = get_effective_config()
                query = next(
                    (m["content"] for m in reversed(history) if m["role"] == "user"), ""
                )
                results = await web_search(query, cfg.get("web_search_key", ""))
                context = build_search_context(results)
                if context:
                    messages.append({"role": "system", "content": context})
                # 来源清单单独发给前端：渲染为回答下方的「参考文献」区块
                sources = [{"title": r["title"], "url": r["url"]} for r in results]
        except ValueError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
            return
        except (WebSearchNotConfiguredError, WebSearchError) as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
            return
        if sources:
            yield _sse({"sources": sources})
        try:
            async for delta in stream_chat(messages, model=payload.model, deep=payload.deep):
                yield _sse({"delta": delta})
            yield _sse({"done": True})
        except AINotConfiguredError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
        except AIProviderError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
        except Exception:  # noqa: BLE001 兜底：避免未捕获异常直接中断 SSE 流
            yield _sse({"error": "服务内部错误，请稍后重试"})
            yield _sse({"done": True})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/judge-followup")
async def judge_followup(payload: JudgeFollowupRequest):
    """批改后追问：结合题目、学生答案与上轮批改反馈，回答学生对批改的疑问（SSE 流式）。"""
    history = _clean_history(payload.messages)
    return _sse_stream(
        lambda: build_judge_followup_messages(
            payload.lesson_id,
            payload.section_index,
            payload.question,
            payload.answer,
            payload.feedback,
            history,
        )
    )


@router.post("/gen-exercise")
async def gen_exercise(payload: GenExerciseRequest):
    """生成变式应用题：依据原题与学生表现，出同知识点、相近难度的练习题（SSE 流式）。"""
    return _sse_stream(
        lambda: build_gen_exercise_messages(
            payload.lesson_id,
            payload.section_index,
            payload.question,
            payload.answer,
            payload.feedback,
        )
    )


def _parse_quiz_variant(text: str) -> dict | None:
    """从模型输出中提取并校验变式题 JSON（容忍 ```json 围栏与前后缀文字）。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    q = str(data.get("question") or "").strip()
    opts = data.get("options")
    if not q or not isinstance(opts, list) or len(opts) < 2:
        return None
    options = [str(o).strip() for o in opts]
    raw = data.get("answer")
    if isinstance(raw, int):
        answers = [raw]
    elif isinstance(raw, list):
        answers = [a for a in raw if isinstance(a, (int, float))]
    else:
        return None
    ans = [int(a) - 1 for a in answers]
    if not ans or not all(0 <= a < len(options) for a in ans):
        return None
    return {
        "question": q,
        "options": options,
        "answer": ans,
        "explain": str(data.get("explain") or "").strip(),
    }


@router.post("/quiz-variant")
async def quiz_variant(payload: QuizVariantRequest):
    """随堂测验变式题：同知识点、相近难度的单选题（JSON 返回，非流式）。

    成功返回 {"question","options","answer","explain"}；失败返回 {"error"}。
    模型输出非合法 JSON 时带纠偏指令重试一次。
    """
    try:
        messages = build_quiz_variant_messages(
            payload.lesson_id,
            payload.section_index,
            payload.question,
            payload.options,
            payload.correct_indexes,
            payload.user_indexes,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    for attempt in range(2):
        try:
            text = await complete_chat(messages)
        except (AINotConfiguredError, AIProviderError) as e:
            return JSONResponse({"error": str(e)}, status_code=502)
        data = _parse_quiz_variant(text)
        if data:
            return JSONResponse(data)
        if attempt == 0:
            # 纠偏重试：把模型上次输出回灌，明确要求只输出 JSON
            messages = messages + [
                {"role": "assistant", "content": text[:2000]},
                {
                    "role": "user",
                    "content": "上一条输出不是合法 JSON。请只输出符合字段要求的 JSON 对象，"
                    "不要任何解释文字、Markdown 或代码围栏。",
                },
            ]
    return JSONResponse({"error": "AI 生成的变式题格式异常，请重试"}, status_code=502)


@router.post("/plan")
async def plan(payload: PlanRequest):
    """学习路径规划：基于前端汇总的进度数据，输出复习重点与下一步建议（SSE 流式）。"""
    return _sse_stream(lambda: build_plan_messages(payload.summary))


@router.post("/quiz-explain")
async def quiz_explain(payload: QuizExplainRequest):
    """选择题 AI 解析：结合课程小节上下文，讲清正确项与各错误项（SSE 流式）。"""
    return _sse_stream(
        lambda: build_quiz_explain_messages(
            payload.lesson_id,
            payload.section_index,
            payload.question,
            payload.options,
            payload.correct_indexes,
            payload.user_indexes,
        )
    )


@router.post("/lesson-summary")
async def lesson_summary(payload: LessonSummaryRequest):
    """章节小结：基于全课内容生成 3-5 条要点（SSE 流式）。"""
    return _sse_stream(lambda: build_lesson_summary_messages(payload.lesson_id))


@router.post("/review")
async def review(payload: ReviewRequest):
    """错题弱项复习：基于学习进度与错题清单给出复习建议（SSE 流式）。"""
    return _sse_stream(lambda: build_review_messages(payload.summary))


@router.post("/judge")
async def judge_answer(payload: JudgeRequest):
    """批改应用题：结合课程小节上下文判断学生答案，SSE 流式返回批改结果。

    事件：{"delta": str} 增量文本；{"done": true} 结束；{"error": str} 出错。
    """
    async def gen():
        try:
            messages = build_judge_messages(
                payload.lesson_id, payload.section_index, payload.question, payload.answer
            )
        except ValueError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
            return
        try:
            async for delta in stream_chat(messages):
                yield _sse({"delta": delta})
            yield _sse({"done": True})
        except AINotConfiguredError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
        except AIProviderError as e:
            yield _sse({"error": str(e)})
            yield _sse({"done": True})
        except Exception:  # noqa: BLE001 兜底：避免未捕获异常直接中断 SSE 流
            yield _sse({"error": "服务内部错误，请稍后重试"})
            yield _sse({"done": True})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
