#!/usr/bin/env python
"""内容校验脚本：课程 Markdown 的一致性/完整性静态检查 + 纯数学沙箱重放。

用法：
    python scripts/check_content.py            # 全部静态检查 + 纯数学沙箱重放
    python scripts/check_content.py --no-replay # 仅静态检查

检查项：
  1) 全部课程可被 phase_loader 解析，id 与文件名一致；
  2) :::quiz 答案索引落在选项范围内（quiz 块合法）；
  3) :::answer 与 :::exercise 一一配对（应用题均有参考答案要点）；
  4) :::viz 组件名全部在 vizRegistry 注册；
  5) :::code_sandbox 块代码可编译；纯数学沙箱（p1-l3/p5-l1）重放输出与「预期输出」逐行一致；
  6) 残留问题模式扫描（被删词断句、裸 \\sqrt、全角冒号代码、已知错别字）；
  7) 快照日期时效提醒（>90 天的「YYYY-MM-DD 快照」打 warning，不判失败）。
退出码：有 error 则 1，仅 warning 则 0。
"""
import io
import math
import re
import sys
import contextlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

ERRORS: list[str] = []
WARNINGS: list[str] = []


def err(msg: str):
    ERRORS.append(msg)


def warn(msg: str):
    WARNINGS.append(msg)


def load_content():
    from app.services.content.phase_loader import load_all_content
    return load_all_content()


def check_quiz(content):
    for fid, c in content.items():
        for s in c["sections"]:
            for m in re.finditer(r":::quiz\n(.*?)\n:::", s["body"], re.S):
                block = m.group(1)
                am = re.search(r"^A:\s*([\d,，、\s]+)$", block, re.M)
                opts = re.findall(r"^-\s+", block, re.M)
                if not am:
                    err(f"{fid}::{s['title'][:20]} quiz 缺 A: 行")
                    continue
                for a in re.split(r"[,，、\s]+", am.group(1).strip()):
                    if a and not (1 <= int(a) <= len(opts)):
                        err(f"{fid}::{s['title'][:20]} quiz 答案 {a} 超出选项数 {len(opts)}")


def check_answer_pairing(content):
    for fid, c in content.items():
        for s in c["sections"]:
            n_ex = len(re.findall(r"^:::exercise", s["body"], re.M))
            n_ans = len(re.findall(r"^:::answer", s["body"], re.M))
            if n_ex != n_ans:
                err(f"{fid}::{s['title'][:20]} 应用题 {n_ex} 道 vs 答案 {n_ans} 条")


def check_viz_registry(content):
    ts = (ROOT / "frontend/src/components/lesson/vizRegistry.ts").read_text()
    keys = set(re.findall(r"^\s{2}([a-z_0-9]+):\s*def\(", ts, re.M))
    for fid, c in content.items():
        for s in c["sections"]:
            for m in re.finditer(r":::viz\s+([a-z_0-9]+)", s["body"]):
                if m.group(1) not in keys:
                    err(f"{fid} viz 组件未注册: {m.group(1)}")


def extract_sandboxes(content):
    blocks = {}
    for fid, c in content.items():
        for s in c["sections"]:
            for m in re.finditer(r":::viz code_sandbox[^\n]*\n(.*?)\n:::", s["body"], re.S):
                body = m.group(1)
                marker = "# === 预期输出 ==="
                if marker in body:
                    code, expected = body.split(marker)
                    blocks.setdefault(fid, (code.rstrip(), expected.strip()))
                else:
                    blocks.setdefault(fid, (body, ""))
    return blocks


def check_sandbox_syntax(blocks):
    for fid, (code, _) in blocks.items():
        try:
            compile(code, fid, "exec")
        except SyntaxError as e:
            err(f"{fid} 沙箱代码语法错误: {e}")


def replay_sandbox(fid, code, expected):
    ns = {"math": math, "__name__": "__main__"}
    try:
        import numpy as np
        ns["np"] = np
    except ImportError:
        warn("numpy 不可用，跳过沙箱重放")
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        pass
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(code, fid, "exec"), ns)
    except Exception as e:  # noqa: BLE001
        err(f"{fid} 沙箱重放抛出异常: {type(e).__name__}: {e}")
        return
    got = [l.strip() for l in buf.getvalue().splitlines() if l.strip()]
    exp = [l.strip() for l in expected.splitlines() if l.strip()]
    if len(got) != len(exp):
        err(f"{fid} 沙箱输出行数 {len(got)} != 预期 {len(exp)}")
        return
    for i, (g, e) in enumerate(zip(got, exp), 1):
        if g != e:
            err(f"{fid} 沙箱输出第 {i} 行不一致:\n  got: {g}\n  exp: {e}")


# 纯数学沙箱（不依赖数据库，输出确定性可复现）——新增纯数学沙箱后在此登记
PURE_MATH_SANDBOXES = {"p0-l1", "p0-l2", "p0-l4", "p1-l3", "p5-l1"}


def check_stale_patterns(content):
    # 数学定界符外的裸 \sqrt：把同一行内所有 $...$ 片段删掉后再找
    def raw_latex_outside_math(body: str):
        hits = []
        for lineno, line in enumerate(body.splitlines(), 1):
            stripped = re.sub(r"\$[^$]*\$", "", re.sub(r"\$\$[^$]*?\$\$", "", line))
            if re.search(r"\\sqrt\{", stripped):
                hits.append((lineno, line))
        return hits

    patterns = [
        (r"(^|[\s（])的 161 因子库就是|来自 ，|（ 宏观|。 中计算|因为 暂无", "被删词断句"),
        (r"rs\.next()：", "代码内全角冒号"),
        (r"可可靠|的 的|是 是的", "疑似错别字"),
    ]
    for fid, c in content.items():
        for s in c["sections"]:
            for pat, label in patterns:
                m = re.search(pat, s["body"])
                if m:
                    err(f"{fid}::{s['title'][:20]} {label}: …{s['body'][max(0, m.start()-20):m.end()+20]}…")
            for lineno, line in raw_latex_outside_math(s["body"]):
                err(f"{fid}::{s['title'][:20]} 第{lineno}行数学定界符外的裸 \\sqrt: {line.strip()[:60]}")


def check_snapshot_freshness(content):
    today = date.today()
    for fid, c in content.items():
        for s in c["sections"]:
            for m in re.finditer(r"(\d{4}-\d{2}-\d{2})\s*快照", s["body"]):
                try:
                    d = date.fromisoformat(m.group(1))
                except ValueError:
                    continue
                age = (today - d).days
                if age > 90:
                    warn(f"{fid} 含 {m.group(1)} 快照（已 {age} 天），确认数据是否需要更新")


def main():
    no_replay = "--no-replay" in sys.argv
    content = load_content()
    print(f"[1] 课程解析: {len(content)} 课")
    if len(content) < 60:
        err(f"课程数异常: {len(content)} < 60")
    ids_in_files = {p.stem for p in (ROOT / "backend/app/content").rglob("*.md")}
    missing = ids_in_files - set(content)
    if missing:
        err(f"以下文件缺 frontmatter id，未被加载: {sorted(missing)}")

    print("[2] quiz 答案索引")
    check_quiz(content)
    print("[3] 应用题/答案配对")
    check_answer_pairing(content)
    print("[4] viz 组件注册")
    check_viz_registry(content)
    print("[5] 沙箱语法 + 纯数学沙箱重放")
    blocks = extract_sandboxes(content)
    print(f"    沙箱块: {len(blocks)} 个")
    check_sandbox_syntax(blocks)
    if not no_replay:
        for fid in PURE_MATH_SANDBOXES:
            if fid in blocks:
                print(f"    重放 {fid} …")
                replay_sandbox(fid, *blocks[fid])
    print("[6] 残留问题模式")
    check_stale_patterns(content)
    print("[7] 快照时效")
    check_snapshot_freshness(content)

    for w in WARNINGS:
        print(f"WARNING: {w}")
    for e in ERRORS:
        print(f"ERROR: {e}")
    print(f"\n结果: {len(ERRORS)} errors, {len(WARNINGS)} warnings")
    sys.exit(1 if ERRORS else 0)


if __name__ == "__main__":
    main()
