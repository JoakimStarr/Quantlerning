"""Markdown 课程内容加载器。

课程内容以 .md 文件组织在 backend/app/content/phase{0,1,...}/ 下。
每个文件对应一课，格式：

```markdown
---
id: p1-l10
summary: 一句话引言（渲染为蓝色引言框）
---

## 小节标题

正文 Markdown（支持 $LaTeX$ 与 :::viz 块）

## 另一小节

...
```

frontmatter 可含任意字段（title/concepts 等），按 ## 拆分 sections。
输出结构与旧 Python dict 内容源一致：
{lesson_id: {"summary": str, "sections": [{"title": str, "body": str}, ...]}}
"""
from pathlib import Path

import frontmatter

CONTENT_DIR = Path(__file__).resolve().parent.parent.parent / "content"  # backend/app/content


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter（--- 包裹的头块），返回 (字段dict, 正文)。

    用 python-frontmatter（PyYAML）解析，支持多行/列表/引号内冒号等完整 YAML；
    无 frontmatter 或 YAML 异常时按无头块处理（返回空字段与原文），不阻塞加载。
    """
    try:
        post = frontmatter.loads(text)
    except Exception:  # noqa: BLE001 坏 frontmatter 不阻塞整库加载
        return {}, text
    return dict(post.metadata or {}), post.content


def _split_sections(body: str) -> list[dict]:
    """按 ## 标题拆分成 sections（忽略代码块内的 ##）。返回 [{title, body}]。"""
    sections: list[dict] = []
    current_title: str | None = None
    current_parts: list[str] = []
    in_code = False
    for line in body.splitlines(keepends=True):
        stripped = line.strip()
        # 切换代码块状态（``` 围栏）
        if stripped.startswith("```"):
            in_code = not in_code
            current_parts.append(line)
            continue
        if line.startswith("## ") and not in_code:
            if current_title is not None:
                sections.append({"title": current_title, "body": "".join(current_parts).strip()})
                current_parts = []
            # 首个 ## 之前未命名的引言段落：不重置 parts，并入第一个小节开头，避免静默丢失
            current_title = line[3:].strip()
        else:
            current_parts.append(line)
    if current_title is not None:
        sections.append({"title": current_title, "body": "".join(current_parts).strip()})
    elif "".join(current_parts).strip():
        # 全文无 ## 标题：整篇作为一个无标题小节，避免内容被丢弃
        sections.append({"title": "", "body": "".join(current_parts).strip()})
    return sections


def _load_one_file(path: Path) -> tuple[str, dict] | None:
    """加载单个 .md 文件 → (lesson_id, content)。"""
    text = path.read_text(encoding="utf-8")
    fields, body = _parse_frontmatter(text)
    lesson_id = fields.get("id")
    if not lesson_id:
        return None
    summary = fields.get("summary", "")
    sections = _split_sections(body)
    content = {"summary": summary, "sections": sections}
    for k, v in fields.items():
        if k not in ("id", "summary"):
            content[k] = v
    return lesson_id, content


def load_all_content() -> dict:
    """扫描 content/ 下所有 .md，返回 {lesson_id: {summary, sections, ...}}。"""
    result: dict = {}
    if not CONTENT_DIR.exists():
        return result
    for path in sorted(CONTENT_DIR.rglob("*.md")):
        loaded = _load_one_file(path)
        if loaded:
            lesson_id, content = loaded
            result[lesson_id] = content
    return result


def _md_snapshot() -> dict[Path, int]:
    """当前所有 .md 的 (路径 → mtime_ns)，用于检测增/删/改。"""
    if not CONTENT_DIR.exists():
        return {}
    return {p: p.stat().st_mtime_ns for p in sorted(CONTENT_DIR.rglob("*.md"))}


# 惰性重载缓存：首次调用或任一 .md 变化时重建，否则复用
_cache: dict | None = None
_cache_snapshot: dict[Path, int] | None = None


def get_content() -> dict:
    """返回课程内容，带 mtime 检查的惰性重载。

    开发期改动 Markdown 文件后，前端刷新即可看到新内容，无需重启后端；
    文件未变化时直接返回缓存，避免每次请求重新解析。
    """
    global _cache, _cache_snapshot
    snapshot = _md_snapshot()
    if _cache is None or _cache_snapshot != snapshot:
        _cache = load_all_content()
        _cache_snapshot = snapshot
    return _cache
