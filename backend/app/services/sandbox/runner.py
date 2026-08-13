"""练习沙箱执行器（作为独立子进程运行，勿直接 import）。

流程：主进程经 AST 白名单检查后，以 `python -I runner.py <base64(code)>` 拉起本文件；
本进程先设置资源上限（CPU/内存/文件/进程数），再在受限命名空间中 exec 用户代码。
用户代码可用的数据对象：`get_daily(code, start, end)` —— 只读查询 quantlab 库。
"""
import base64
import os
import resource
import sys

# 资源上限（与 PLAN 沙箱约束对应）
_CPU_SECONDS = 6
_MEMORY_BYTES = 1024 * 1024 * 1024  # 1GB 虚拟地址空间（pandas+numpy+线程栈；PLAN 256MB 偏紧，放宽）
_FILE_SIZE = 1024 * 1024  # 文件写 1MB
_MAX_PROC = 1024  # 进程/线程数上限（RLIMIT_NPROC 对 uid 全局生效，须高于正常负载）


def apply_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (_CPU_SECONDS, _CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (_MEMORY_BYTES, _MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (_FILE_SIZE, _FILE_SIZE))
    resource.setrlimit(resource.RLIMIT_NPROC, (_MAX_PROC, _MAX_PROC))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


def _get_daily(code: str, start: str = "2018-01-01", end: str | None = None, limit: int = 100000):
    """只读查询 quantlab 库个股日线（复权口径 close、pct_chg），返回 pandas DataFrame。

    连接串由主进程经环境变量 QL_DB_URL 传入（asyncpg 协议）。
    end 缺省为今天（数据随库自动更新，不会过期）；limit 防止全量拉取。
    """
    import asyncio
    import asyncpg

    import pandas as pd

    url = os.environ.get("QL_DB_URL", "")
    if not url:
        raise RuntimeError("数据库连接未配置")
    end = end or _today()

    async def _fetch():
        from datetime import date

        conn = await asyncpg.connect(url)
        try:
            rows = await conn.fetch(
                "SELECT trade_date, close, pct_chg FROM stock_daily "
                "WHERE UPPER(code) = $1 AND trade_date BETWEEN $2 AND $3 "
                "ORDER BY trade_date LIMIT $4",
                code.upper(),
                date.fromisoformat(start),
                date.fromisoformat(end),
                limit,
            )
        finally:
            await conn.close()
        return rows

    rows = asyncio.run(_fetch())
    return pd.DataFrame(
        [
            {"date": str(r["trade_date"]), "close": float(r["close"]), "pct_chg": float(r["pct_chg"])}
            for r in rows
        ]
    )


def _get_index(indicator: str, start: str = "2018-01-01", end: str | None = None, limit: int = 100000):
    """只读查询 quantlab 库指数日收盘（macro_indicator，如 SH_INDEX→sh_idx_close）。

    返回与 get_daily 同构的 DataFrame（date、close、pct_chg），便于与个股日线 merge 后回归。
    """
    import asyncio
    import asyncpg

    import pandas as pd

    url = os.environ.get("QL_DB_URL", "")
    if not url:
        raise RuntimeError("数据库连接未配置")
    end = end or _today()

    async def _fetch():
        from datetime import date

        conn = await asyncpg.connect(url)
        try:
            rows = await conn.fetch(
                "SELECT report_date, value FROM macro_indicator "
                "WHERE indicator = $1 AND field_name = 'sh_idx_close' "
                "AND report_date BETWEEN $2 AND $3 ORDER BY report_date LIMIT $4",
                indicator,
                date.fromisoformat(start),
                date.fromisoformat(end),
                limit,
            )
        finally:
            await conn.close()
        return rows

    rows = asyncio.run(_fetch())
    if not rows:
        raise ValueError(f"指数 {indicator} 无日收盘数据（当前仅 SH_INDEX 上证指数可用）")
    df = pd.DataFrame(
        [
            {"date": str(r["report_date"]), "close": float(r["value"])}
            for r in rows
        ]
    )
    df["pct_chg"] = df["close"].pct_change() * 100
    return df


def main() -> None:
    apply_limits()
    # 无交互后端：matplotlib 用 Agg，图片由 _emit_images 捕获为 base64，不经显示器
    os.environ.setdefault("MPLBACKEND", "Agg")
    try:
        code = base64.b64decode(sys.argv[1]).decode("utf-8")
    except Exception:  # noqa: BLE001
        print("参数错误：无法解码练习代码", file=sys.stderr)
        sys.exit(1)

    import collections
    import datetime
    import functools
    import itertools
    import math
    import random
    import statistics

    import numpy as np
    import pandas as pd

    # 教学沙箱：屏蔽非交互后端等噪音警告，保持输出干净（真实错误仍会抛出）
    import warnings

    warnings.filterwarnings("ignore")

    # 受限命名空间：白名单库 + 只读数据对象；不含可逃逸的敏感对象
    ns = {
        "__name__": "__main__",
        "math": math,
        "statistics": statistics,
        "random": random,
        "itertools": itertools,
        "functools": functools,
        "collections": collections,
        "datetime": datetime,
        "np": np,
        "pd": pd,
        "get_daily": _get_daily,
        "get_index": _get_index,
    }

    try:
        exec(compile(code, "<练习代码>", "exec"), ns)
    except SystemExit:
        pass  # 用户显式 exit 视为正常结束
    except BaseException as e:  # noqa: BLE001
        # 定位到用户代码中的出错行（帧文件名为 <练习代码>），方便前端高亮
        lineno = None
        tb = sys.exc_info()[2]
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == "<练习代码>":
                lineno = tb.tb_lineno
            tb = tb.tb_next
        msg = f"{type(e).__name__}: {e}"
        print(f"第 {lineno} 行: {msg}" if lineno else msg, file=sys.stderr)
        sys.exit(1)

    _emit_images()


def _emit_images() -> None:
    """把 matplotlib 打开中的图形以 base64 PNG 输出到 stdout（__SANDBOX_IMG__ 前缀行）。

    exec.py 解析该标记并把图片移到响应 images 字段，避免污染 stdout 文本。
    """
    try:
        import base64 as b64
        import io

        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001
        return
    for num in plt.get_fignums():
        try:
            fig = plt.figure(num)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
            buf.seek(0)
            print(f"__SANDBOX_IMG__{b64.b64encode(buf.getvalue()).decode('ascii')}")
            plt.close(fig)
        except Exception:  # noqa: BLE001
            continue


if __name__ == "__main__":
    main()
