#!/usr/bin/env python3
"""导出最小可运行数据集：quantlab 库 → data/quantlerning_sample.sql.gz

供贡献者本地一键恢复（无需连接原始 quantlab 库）：

    createdb quantlab
    gunzip -c quantlerning_sample.sql.gz | psql -d quantlab

数据范围（够跑通全部课程/模拟器，远小于全库）：
- stock_daily：5 只核心股（茅台/五粮液/宁德/平安银行/中国平安）全历史
               + 按行业、按近两年成交额抽样的横截面股票池（默认 800 只）全历史
- etf_daily：SH510050 示例（前端当前未使用，保留让 /index/* 端点不报错）
- stock_basic / stock_index / stock_industry / factor / strategy / backtest_result：全量
- macro_indicator：前端实际使用的 CPI / PPI / SH_INDEX / TREASURY / LPR

用法：
    python scripts/export_sample.py [--out data/quantlerning_sample.sql.gz] [--universe 800]

依赖：本机可连 quantlab 库、已安装 pg_dump 与 Python asyncpg。
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import io
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import settings  # noqa: E402  (先插 sys.path 再导入)

CORE_CODES = ["SH600519", "SZ000858", "SZ300750", "SZ000001", "SH601318"]

# 全量导出的小表
FULL_TABLES = ["stock_basic", "stock_index", "stock_industry", "factor", "strategy", "backtest_result"]

# macro_indicator：只取前端/内容实际用到的指标
MACRO_INDICATORS = ["CPI", "PPI", "SH_INDEX", "TREASURY", "LPR"]


# 数值列：横截面非核心股四舍五入到 4 位小数以压缩体积（核心股保持原精度）
STOCK_DAILY_NUMERIC = [
    "open", "high", "low", "close", "preclose", "volume", "amount",
    "turn", "pct_chg", "pe_ttm", "pb_mrq", "ps_ttm", "pcf_ncf_ttm",
]


async def _stock_daily_select(conn) -> list[str]:
    """stock_daily 的 SELECT 列表达式：核心股原值，横截面股 ROUND(·,4)。"""
    cols = await _columns(conn, "stock_daily")
    core = ", ".join(f"'{c}'" for c in CORE_CODES)
    out: list[str] = []
    for c in cols:
        if c in STOCK_DAILY_NUMERIC:
            out.append(f"CASE WHEN code IN ({core}) THEN {c}::text ELSE ROUND({c}::numeric, 4)::text END AS {c}")
        else:
            out.append(c)
    return out


async def _columns(conn, table: str) -> list[str]:
    """按 ordinal_position 返回表的列名列表（与 CREATE TABLE 顺序一致）。"""
    rows = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )
    return [r["column_name"] for r in rows]


async def pick_universe(conn, n: int) -> list[str]:
    """按行业分层 + 近期成交额排序，确定横截面股票池（确定性抽样）。

    - 候选：当前上市（status='1'）且有行业映射的股票（行业 PE 模拟器依赖行业字段）
    - 行业内按 2024 年以来日均成交额降序取前 quota（配额与行业规模成正比，每行业至少 1 只）
    - 超/缺时按全局成交额调整到恰好 n 只；最后强制并入 5 只核心股
    """
    liq_rows = await conn.fetch(
        """
        SELECT code, AVG(amount) AS liq FROM stock_daily
        WHERE trade_date >= '2024-01-01'
        GROUP BY code
        """
    )
    # stock_daily.code 为大写，stock_industry/stock_basic 为小写，统一按大写比较
    liq = {r["code"].upper(): r["liq"] or 0.0 for r in liq_rows}
    cand = await conn.fetch(
        """
        SELECT si.code, si.industry
        FROM stock_industry si
        JOIN stock_basic sb ON sb.code = si.code AND sb.status = '1'
        WHERE si.industry <> ''
        """
    )
    by_ind: dict[str, list[str]] = {}
    for r in cand:
        by_ind.setdefault(r["industry"], []).append(r["code"].upper())
    total = sum(len(v) for v in by_ind.values())
    if total == 0:
        raise RuntimeError("无符合条件的横截面候选股票（检查 stock_industry / stock_basic）")

    chosen: set[str] = set()
    for ind, codes in by_ind.items():
        quota = max(1, round(n * len(codes) / total))
        chosen.update(sorted(codes, key=lambda c: (-liq.get(c, 0.0), c))[:quota])

    all_cand = {r["code"].upper() for r in cand}
    # 超了：按全局流动性裁到 n
    if len(chosen) > n:
        chosen = set(sorted(chosen, key=lambda c: (-liq.get(c, 0.0), c))[:n])
    # 不够：从剩余候选中按流动性补齐
    if len(chosen) < n:
        rest = [c for c in all_cand - chosen]
        rest.sort(key=lambda c: (-liq.get(c, 0.0), c))
        chosen.update(rest[: n - len(chosen)])
    chosen.update(CORE_CODES)
    return sorted(chosen)


def _pgdump_schema(db_url_env: dict, tables: list[str]) -> bytes:
    """用 pg_dump --schema-only 生成建表 DDL，剥掉 OWNER/GRANT/REVOKE。"""
    args = [
        "pg_dump",
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "--no-comments",
        "--dbname", db_url_env["PGDATABASE"],
    ]
    for t in tables:
        args += ["--table", f"public.{t}"]
    proc = subprocess.run(args, env={**os.environ, **db_url_env}, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump 失败：{proc.stderr[:800]}")
    return proc.stdout.encode()


async def export(out_path: Path, universe_n: int) -> dict[str, int]:
    dsn = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    import asyncpg

    conn = await asyncpg.connect(dsn)
    counts: dict[str, int] = {}
    try:
        universe = await pick_universe(conn, universe_n)

        # 各表的数据子集：where 子句 + 可选的自定义 SELECT 列表达式
        # 横截面股票池（非核心股）数值列四舍五入到 4 位小数，压缩体积；
        # 核心 5 股保持原精度，保证主线数字与沙箱预期输出一致。
        stock_select = await _stock_daily_select(conn)
        universe_in = ", ".join(f"'{c}'" for c in universe)
        where_sql: dict[str, tuple[str, list[str]]] = {
            "stock_daily": (f"WHERE code IN ({universe_in})", stock_select),
            "etf_daily": ("WHERE code = 'SH510050'", []),
            "macro_indicator": ("WHERE indicator IN ('" + "','".join(MACRO_INDICATORS) + "')", []),
        }
        for t in FULL_TABLES:
            where_sql[t] = ("", [])

        tables = ["stock_daily", "etf_daily"] + FULL_TABLES + ["macro_indicator"]
        schema = _pgdump_schema(
            {
                "PGUSER": settings.postgres_user,
                "PGPASSWORD": settings.postgres_password,
                "PGHOST": settings.postgres_host,
                "PGPORT": str(settings.postgres_port),
                "PGDATABASE": settings.postgres_db,
            },
            tables,
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(out_path, "wb") as gz:
            def write(b: bytes) -> None:
                gz.write(b)

            write(b"-- Quantlerning sample dataset (auto-generated, do not edit)\n")
            write(b"-- Regenerate: python scripts/export_sample.py\n")
            write(b"SET client_encoding = 'UTF8';\n")
            write(b"SET standard_conforming_strings = on;\n\n")
            write(schema)
            write(b"\n")
            for t in tables:
                cols = await _columns(conn, t)
                where, select_expr = where_sql[t]
                col_list = ", ".join(select_expr) if select_expr else ", ".join(cols)
                query = f"SELECT {col_list} FROM {t} {where}".rstrip()
                n = await conn.fetchval(f"SELECT COUNT(*) FROM {t} {where}".rstrip())
                counts[t] = n
                write(f"COPY public.{t} ({', '.join(cols)}) FROM stdin;\n".encode())
                buf = io.BytesIO()
                await conn.copy_from_query(query, output=buf)
                write(buf.getvalue())
                write(b"\\.\n")
            write(b"\n-- done\n")
    finally:
        await conn.close()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 Quantlerning 最小数据集")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "quantlerning_sample.sql.gz")
    parser.add_argument("--universe", type=int, default=800, help="横截面股票池数量（默认 800）")
    args = parser.parse_args()

    counts = asyncio.run(export(args.out, args.universe))
    size_mb = args.out.stat().st_size / 1024 / 1024
    print(f"✓ 已导出 → {args.out}")
    print(f"  体积: {size_mb:.1f} MB")
    for t, n in counts.items():
        print(f"  {t:18s} {n:>10,} 行")


if __name__ == "__main__":
    main()
