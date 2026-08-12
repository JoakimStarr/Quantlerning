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


def _get_daily(code: str, start: str = "2018-01-01", end: str = "2026-08-10"):
    """只读查询 quantlab 库个股日线（复权口径 close、pct_chg），返回 pandas DataFrame。

    连接串由主进程经环境变量 QL_DB_URL 传入（asyncpg 协议）。
    """
    import asyncio
    import asyncpg

    import pandas as pd

    url = os.environ.get("QL_DB_URL", "")
    if not url:
        raise RuntimeError("数据库连接未配置")

    async def _fetch():
        from datetime import date

        conn = await asyncpg.connect(url)
        try:
            rows = await conn.fetch(
                "SELECT trade_date, close, pct_chg FROM stock_daily "
                "WHERE UPPER(code) = $1 AND trade_date BETWEEN $2 AND $3 "
                "ORDER BY trade_date",
                code.upper(),
                date.fromisoformat(start),
                date.fromisoformat(end),
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


def main() -> None:
    apply_limits()
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
    }

    try:
        exec(compile(code, "<练习代码>", "exec"), ns)
    except SystemExit:
        pass  # 用户显式 exit 视为正常结束
    except BaseException as e:  # noqa: BLE001
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
