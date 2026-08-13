"""AI 追问路由：POST /api/v1/chat/stream（SSE 流式）。"""
import json
from collections.abc import Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services.ai.chat import (
    AINotConfiguredError,
    AIProviderError,
    build_gen_exercise_messages,
    build_judge_followup_messages,
    build_judge_messages,
    build_messages,
    build_plan_messages,
    stream_chat,
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


class PlanRequest(BaseModel):
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
        try:
            messages = build_messages(payload.lesson_id, payload.section_index, history)
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


@router.post("/plan")
async def plan(payload: PlanRequest):
    """学习路径规划：基于前端汇总的进度数据，输出复习重点与下一步建议（SSE 流式）。"""
    return _sse_stream(lambda: build_plan_messages(payload.summary))


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
