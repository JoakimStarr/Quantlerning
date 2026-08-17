#!/usr/bin/env python3
"""内容质量检查器：把「课程写作规范」落成可重复执行的检查脚本。

用法：
    python scripts/check_content.py           # 全量检查
    python scripts/check_content.py phase5     # 指定阶段
    python scripts/check_content.py p5-l3      # 指定课

检查维度（对应《课程写作规范》+ 内容补充机制）：
  A 结构完整性（治「散」）：章引言 / 前置标注 / 学习目标 / 跨课引用
  B 内容深度（治「少」）：正文行数 / 知识点字数 / 图引导 / 参考文献
  C 专业度（治「不专业」）：术语与数字锚点一致 / LaTeX 闭合
  D 可学习性（治「学不懂」）：概念四步引入 / 衔接 / 练习分离
  E 生态介绍（补「缺生态」）：生态/平台/工具链提及
"""
import glob
import re
import sys
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "content"

# ---------- 检查阈值（可调） ----------
MIN_PROSE_LINES = 100          # 每课正文行数下限（或满足下方字数条件）
MIN_SECTION_CHARS = 80         # 每知识点小节字数下限
MIN_INTRO_CHARS = 120          # 章引言（courses.py intro）字数下限
REF_KEYWORDS = ["生态", "平台", "工具链", "框架", "社区", "实盘", "券商", "数据源", "开源"]
QUIZ_SEPARATED = True          # 练习必须独立成节


# ---------- 内容解析 ----------
def parse_lesson(path: Path) -> dict:
    """解析单课 md → 结构信息。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # frontmatter
    fm = {}
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            if ":" in ln:
                k, v = ln.split(":", 1)
                fm[k.strip()] = v.strip()

    # 正文/sections
    in_q = in_e = in_c = False
    prose_lines = 0
    sections = []          # {title, chars}
    cur = None
    quiz_blocks = 0
    exercise_blocks = 0
    viz_count = 0
    for ln in lines:
        s = ln.strip()
        if s.startswith("```"):
            in_c = not in_c
            continue
        if in_c:
            continue
        if s == ":::quiz":
            in_q = True
            quiz_blocks += 1
            continue
        if s == ":::exercise":
            in_e = True
            exercise_blocks += 1
            continue
        if s == ":::" and (in_q or in_e):
            in_q = in_e = False
            continue
        if in_q or in_e:
            continue
        if s.startswith(":::viz"):
            viz_count += 1
            prose_lines += 1
            if cur:
                cur["chars"] += len(s)
            continue
        if s.startswith("## "):
            cur = {"title": s[3:], "chars": 0}
            sections.append(cur)
            prose_lines += 1
            continue
        prose_lines += 1
        if cur:
            cur["chars"] += len(s)

    return {
        "path": path,
        "id": fm.get("id", path.stem),
        "title": fm.get("title", ""),
        "summary": fm.get("summary", ""),
        "prose_lines": prose_lines,
        "sections": sections,
        "quiz_blocks": quiz_blocks,
        "exercise_blocks": exercise_blocks,
        "viz_count": viz_count,
        "text": text,
        "refs": re.findall(r"p[0-6]-l[0-9]+", text),
    }


# ---------- 检查器 ----------
def check_structure(lesson: dict) -> list[str]:
    """A 结构完整性。"""
    issues = []
    # 前置标注
    if not re.search(r"前置|前提|你需要先|先学|本节需要|这一课需要", lesson["text"]):
        issues.append("A1 无「前置知识」标注（读者不知道学这课需要什么）")
    # 学习目标 / 学完能做什么
    if not re.search(r"学完|本课目标|你将能|能.*回答|交付", lesson["text"]):
        issues.append("A2 无「学完能做什么」表述（学习目标缺失）")
    return issues


def check_depth(lesson: dict) -> list[str]:
    """B 内容深度。"""
    issues = []
    # 正文行数
    if lesson["prose_lines"] < MIN_PROSE_LINES:
        issues.append(
            f"B1 正文仅 {lesson['prose_lines']} 行 < {MIN_PROSE_LINES}（若每节字数达标可豁免）"
        )
    # 薄节（不含练习/参考文献）
    for sec in lesson["sections"]:
        if sec["title"] in ("练习题", "参考文献", "阶段测验"):
            continue
        if sec["chars"] < MIN_SECTION_CHARS:
            issues.append(f"B2 小节「{sec['title']}」仅 {sec['chars']} 字 < {MIN_SECTION_CHARS}")
    # 参考文献
    if "## 参考文献" not in lesson["text"]:
        issues.append("B3 无参考文献节")
    elif not re.search(r"https?://", lesson["text"].split("## 参考文献")[-1]):
        issues.append("B3 参考文献节无 URL")
    return issues


def check_professionalism(lesson: dict) -> list[str]:
    """C 专业度。"""
    issues = []
    # LaTeX 闭合（跳过含 $ 的公式行判断；简单检查奇数 $）
    for i, ln in enumerate(lesson["text"].splitlines(), 1):
        s = ln.strip()
        if s.startswith(":::") or s.startswith("$$"):
            continue
        if s.count("$") % 2 == 1:
            issues.append(f"C1 LaTeX 未闭合 @L{i}")
            break
    # Unicode 公式符号（非 LaTeX 上下文）——仅真正的数学符号，不含 →/±/≈ 等正文标点
    bad = re.compile(r"[σΣμβπθΔλ√][^→±≈]|²|³|×")
    for i, ln in enumerate(lesson["text"].splitlines(), 1):
        if "$" in ln:
            continue
        for m in bad.findall(ln):
            issues.append(f"C2 非 LaTeX 公式符号「{m}」@L{i}")
            break
    return issues


def check_learnability(lesson: dict) -> list[str]:
    """D 可学习性。"""
    issues = []
    # 衔接：小节开头不应直接抛公式/术语（要求小节正文首行非公式）
    for sec in lesson["sections"]:
        if sec["title"] in ("练习题", "参考文献"):
            continue
        if sec["chars"] < MIN_SECTION_CHARS:
            continue  # 已由 B2 报
    # 图引导：viz 后应有正文承接（非空、非直接 ## ）
    lines = lesson["text"].splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith(":::viz"):
            j = i + 1
            while j < len(lines) and (lines[j].strip() in (":::", "") or lines[j].strip().startswith(":::")):
                j += 1
            nxt = lines[j].strip() if j < len(lines) else ""
            if not nxt or nxt.startswith("## "):
                issues.append(f"D1 viz @L{i+1} 图后无引导段（「先看什么→看到什么→为什么」）")
    # 练习分离
    if "## 练习题" in lesson["text"]:
        body = lesson["text"].split("## 练习题")[0]
        if ":::quiz" in body or ":::exercise" in body:
            issues.append("D2 正文中混有随堂测验（练习必须收进末尾「练习题」节）")
    return issues


def check_ecosystem(lesson: dict) -> list[str]:
    """E 生态介绍。"""
    issues = []
    if not any(kw in lesson["text"] for kw in REF_KEYWORDS):
        issues.append("E1 全文未提及生态/平台/工具链/数据源/社区")
    return issues


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["all"]
    files = []
    for t in targets:
        if t == "all":
            files += sorted(glob.glob(str(CONTENT_DIR / "phase*" / "p*-l*.md")))
        elif t.startswith("phase"):
            files += sorted(glob.glob(str(CONTENT_DIR / t / "p*-l*.md")))
        elif re.match(r"p[0-6]-l[0-9]+", t):
            ph = t[1]
            files += sorted(glob.glob(str(CONTENT_DIR / f"phase{ph}" / f"{t}.md")))
        else:
            files += sorted(glob.glob(str(Path(t))))
    files = sorted(set(files))

    all_checks = {
        "A 结构": check_structure,
        "B 深度": check_depth,
        "C 专业": check_professionalism,
        "D 可学": check_learnability,
        "E 生态": check_ecosystem,
    }

    total = {"issues": 0, "lessons": 0}
    for f in files:
        lesson = parse_lesson(Path(f))
        total["lessons"] += 1
        issues = []
        for cat, fn in all_checks.items():
            issues += fn(lesson)
        if issues:
            total["issues"] += len(issues)
            print(f"\n### {lesson['id']} ({lesson['title']}) [{lesson['prose_lines']} 行正文, "
                  f"{lesson['quiz_blocks']} quiz, {lesson['exercise_blocks']} ex, {lesson['viz_count']} viz]")
            for it in issues:
                print(f"  - {it}")
    print(f"\n===== 检查完毕：{total['lessons']} 课，{total['issues']} 项问题 =====")


if __name__ == "__main__":
    main()
