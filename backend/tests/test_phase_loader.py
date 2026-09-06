"""phase_loader 边界用例：历史上曾出现「静默丢内容」隐患（CONTENT_REVIEW P1-F）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.content.phase_loader import _split_sections, load_all_content  # noqa: E402


def test_sections_preserve_preamble_before_first_heading():
    """首个 ## 之前的正文不能被静默丢弃（并入第一小节）。"""
    body = "这段引言在第一个标题之前。\n\n## 第一节\n内容A\n\n## 第二节\n内容B\n"
    sections = _split_sections(body)
    assert len(sections) == 2
    assert "这段引言" in sections[0]["body"]
    assert sections[0]["title"] == "第一节"
    assert sections[1]["body"].strip() == "内容B"


def test_sections_ignore_hash_inside_code_block():
    """代码块内的 ## 不是标题。"""
    body = "## 第一节\n```python\n# 不是标题\nx = 1\n```\n尾巴\n"
    sections = _split_sections(body)
    assert len(sections) == 1


def test_no_heading_body_becomes_single_section():
    """全文无 ## 时整篇作为单节，不丢内容。"""
    sections = _split_sections("没有标题的正文\n第二行\n")
    assert len(sections) == 1
    assert "第二行" in sections[0]["body"]


def test_load_all_content_expected_scale():
    """全库 64 课可加载且 id 唯一。"""
    content = load_all_content()
    assert len(content) >= 60
    assert len(content) == len(set(content))
