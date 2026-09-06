#!/usr/bin/env python
"""依赖行情库的沙箱断言（需 QL_DB_URL，CI 中在 postgres service 上运行）。

对每个连库沙箱跑一遍代码，按容差断言关键数字与课程主线一致：
  - p1-l8: 复利累计 -6.24%、年化 -6.51%、年化波动 27.55%、回撤 -27.28%、夏普 -0.31
  - p0-l3: 5 股对齐样本量、茅台/宁德年化波动锚点、协方差正定、组合波动 < 等权
  - p3-l8: shift 合规版与主线表同量级（累计 +31±5pp）、前视版虚高
"""
import io
import math
import os
import re
import sys
import contextlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def _get_daily(code, start="2018-01-01", end=None, limit=100000):
    import asyncio
    import asyncpg
    from datetime import date

    url = os.environ["QL_DB_URL"]
    end = end or date.today().isoformat()

    async def _fetch():
        conn = await asyncpg.connect(url)
        try:
            rows = await conn.fetch(
                "SELECT trade_date, close, pct_chg FROM stock_daily "
                "WHERE UPPER(code) = $1 AND trade_date BETWEEN $2 AND $3 "
                "ORDER BY trade_date LIMIT $4",
                code.upper(), date.fromisoformat(start), date.fromisoformat(end), limit)
        finally:
            await conn.close()
        return rows

    rows = asyncio.run(_fetch())
    return pd.DataFrame([{"date": str(r["trade_date"]), "close": float(r["close"]),
                          "pct_chg": float(r["pct_chg"])} for r in rows])


def load_code(fid: str):
    from app.services.content.phase_loader import load_all_content
    content = load_all_content()
    for s in content[fid]["sections"]:
        for m in re.finditer(r":::viz code_sandbox[^\n]*\n(.*?)\n:::", s["body"], re.S):
            body = m.group(1)
            marker = "# === 预期输出 ==="
            code = body.split(marker)[0].rstrip() if marker in body else body
            return code
    raise RuntimeError(f"{fid} 无沙箱块")


def run(fid: str):
    ns = {"math": math, "np": np, "pd": pd, "get_daily": _get_daily, "__name__": "__main__"}
    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        pass
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        exec(compile(load_code(fid), fid, "exec"), ns)
    return buf.getvalue()


def parse_nums(text: str, keys: list[str]) -> dict:
    """按中文标签提取百分数。"""
    out = {}
    for k in keys:
        m = re.search(k + r"[^\d\-]*(-?[\d.]+)\s*%", text)
        if m:
            out[k] = float(m.group(1))
    return out


def main():
    fails = []

    print("== p1-l8 绩效指标 vs 主线")
    out = run("p1-l8")
    nums = parse_nums(out, ["复利累计", "几何年化", "年化波动", "最大回撤"])
    sharpe = re.search(r"夏普\(rf=2%\)\s*(-?[\d.]+)", out)
    checks = [
        ("复利累计", nums.get("复利累计"), -6.24, 0.2),
        ("几何年化", nums.get("几何年化"), -6.51, 0.2),
        ("年化波动", nums.get("年化波动"), 27.55, 0.3),
        ("最大回撤", nums.get("最大回撤"), -27.28, 0.3),
    ]
    for name, got, want, tol in checks:
        if got is None or abs(got - want) > tol:
            fails.append(f"p1-l8 {name}: got {got}, want {want}±{tol}")
    if sharpe and abs(float(sharpe.group(1)) - (-0.31)) > 0.03:
        fails.append(f"p1-l8 夏普: got {sharpe.group(1)}")
    print("   ok" if not fails else f"   FAIL {fails}")

    print("== p0-l3 五股协方差")
    n_fail_before = len(fails)
    out = run("p0-l3")
    m_mao = re.search(r"'茅台':\s*'([\d.]+)%'", out)
    m_ning = re.search(r"'宁德':\s*'([\d.]+)%'", out)
    if not m_mao or abs(float(m_mao.group(1)) - 27.55) > 2:
        fails.append(f"p0-l3 茅台波动锚点: {m_mao and m_mao.group(1)}")
    if not m_ning or abs(float(m_ning.group(1)) - 46) > 3:
        fails.append(f"p0-l3 宁德波动锚点: {m_ning and m_ning.group(1)}")
    if "True" not in out:
        fails.append("p0-l3 协方差非正定")
    vm = re.search(r"倒数波动加权 ([\d.]+)%\s+vs\s+等权 ([\d.]+)%", out)
    if not vm or float(vm.group(1)) >= float(vm.group(2)):
        fails.append("p0-l3 倒数波动加权组合波动未低于等权")
    print("   ok" if len(fails) == n_fail_before else f"   FAIL {fails[n_fail_before:]}")

    print("== p3-l8 回测口径与前视对照")
    n_fail_before = len(fails)
    out = run("p3-l8")
    compliant = re.search(r"合规[^\n]*累计 ([+-][\d.]+)%", out)
    lookahead = re.search(r"前视[^\n]*累计 ([+-][\d.]+)%", out)
    if not compliant or abs(float(compliant.group(1)) - 31.1) > 5:
        fails.append(f"p3-l8 合规版累计: {compliant and compliant.group(1)}（want 31.1±5）")
    if not lookahead or float(lookahead.group(1)) <= float(compliant.group(1)):
        fails.append("p3-l8 前视版未显著虚高于合规版")
    print("   ok" if len(fails) == n_fail_before else f"   FAIL {fails[n_fail_before:]}")

    for f in fails:
        print(f"FAIL: {f}")
    print(f"\n结果: {len(fails)} fails")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
