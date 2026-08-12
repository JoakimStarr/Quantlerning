"""课程路由：课程地图、课程详情。进度统一存前端 localStorage（后端不参与）。"""
from fastapi import APIRouter, HTTPException, Response

from ..services.content.courses import COURSES
from ..services.content.phase_loader import get_content

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("")
async def list_courses():
    """返回课程地图（阶段 + 课程）。"""
    return [
        {
            "phase": p["phase"],
            "title": p["title"],
            "subtitle": p["subtitle"],
            "status": p["status"],
            "weeks": p["weeks"],
            "lessons": p["lessons"],
        }
        for p in COURSES
    ]


@router.get("/{lesson_id}")
async def get_lesson(lesson_id: str, response: Response):
    """返回单课详情（含上一章/下一章导航）。"""
    # 内容可能随 md 文件更新，禁用浏览器缓存保证实时
    response.headers["Cache-Control"] = "no-store"
    # 展平课程列表，按 (phase, index) 排序以计算前后章
    flat = []
    for phase in COURSES:
        for idx, lesson in enumerate(phase["lessons"]):
            flat.append((phase, idx, lesson))
    for i, (phase, idx, lesson) in enumerate(flat):
        if lesson["id"] == lesson_id:
            prev = flat[i - 1][2] if i > 0 else None
            nxt = flat[i + 1][2] if i < len(flat) - 1 else None
            base = {
                **lesson,
                "phase": phase["phase"],
                "phase_title": phase["title"],
                "prev": {"id": prev["id"], "title": prev["title"]} if prev else None,
                "next": {"id": nxt["id"], "title": nxt["title"]} if nxt else None,
                "visualization": None,
                "exercises": [],
                "quiz": [],
            }
            # 从 loader 加载的内容源查找完整内容（md 文件变化时自动重载）
            content = get_content().get(lesson_id)
            if content:
                base.update(summary=content.get("summary", ""), sections=content.get("sections", []))
            else:
                base["content"] = "内容建设中，敬请期待。"
            return base
    raise HTTPException(status_code=404, detail=f"课程 {lesson_id} 不存在")
