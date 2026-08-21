"""数据查询服务：只读真实行情库，封装常用数据查询。"""
from datetime import date

from cachetools import TTLCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---- TTL 缓存（cachetools，线程安全、到期自动清理；真实 DB 查询较重，TTL 5 分钟）----
_cache: TTLCache = TTLCache(maxsize=512, ttl=300)


def _cached(key: str):
    def deco(fn):
        async def wrapper(db, *args, **kwargs):
            # 键必须包含函数参数：换参（日期区间/组数/bins/limit）不得命中旧缓存
            param_key = repr(args) + repr(sorted(kwargs.items()))
            cache_key = f"{key}:{param_key}"
            hit = _cache.get(cache_key)
            if hit is not None:
                return hit
            result = await fn(db, *args, **kwargs)
            _cache[cache_key] = result
            return result

        return wrapper

    return deco


@_cached("stock_daily")
async def get_stock_daily(
    db: AsyncSession, code: str, start: date, end: date, limit: int = 5000
) -> list[dict]:
    """个股日线（stock_daily.code 为大写，如 SH600519）。"""
    q = text(
        """
        SELECT trade_date, open, high, low, close, volume, amount,
               pct_chg, turn, pe_ttm, pb_mrq
        FROM stock_daily
        WHERE UPPER(code) = :code AND trade_date BETWEEN :start AND :end
        ORDER BY trade_date
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"code": code.upper(), "start": start, "end": end, "limit": limit})
    return [
        {
            "date": str(r.trade_date),
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
            "amount": r.amount,
            "pct_chg": r.pct_chg,
            "turn": r.turn,
            "pe_ttm": r.pe_ttm,
            "pb_mrq": r.pb_mrq,
        }
        for r in rows
    ]


@_cached("stock_financials")
async def get_stock_financials(
    db: AsyncSession, code: str, limit: int = 24
) -> dict:
    """个股财务指标（financial_indicator 长表 → 按报告期宽表）。

    返回 {code, units, periods}：periods 按报告期倒序（最新在前），
    每个报告期含 available_date（披露日，用于避免前视偏差）与全部字段值；
    units 为字段名 → 单位（如 % / 元）。
    """
    q = text(
        """
        SELECT report_date, field_name, value, unit, available_date
        FROM financial_indicator
        WHERE UPPER(code) = UPPER(:code)
        ORDER BY report_date DESC, field_name
        """
    )
    rows = await db.execute(q, {"code": code})
    units: dict[str, str] = {}
    by_date: dict[str, dict] = {}
    for r in rows:
        rd = str(r.report_date)
        if rd not in by_date:
            by_date[rd] = {"report_date": rd, "available_date": str(r.available_date)}
        by_date[rd][r.field_name] = r.value
        units.setdefault(r.field_name, r.unit)
    periods = list(by_date.values())[:limit]
    # 归一为大写返回，与 get_stock_daily 等查询口径一致（避免调用方拿到小写 code 造成拼接不一致）
    return {"code": code.upper(), "units": units, "periods": periods}


@_cached("index_daily")
async def get_index_daily(
    db: AsyncSession, code: str, start: date, end: date, limit: int = 5000
) -> list[dict]:
    """指数/ETF 日线（从 etf_daily 查询，code 如 SH510050）。

    宽基指数（如 sh000300）日线在本地行情库中，
    M0 阶段先用 etf_daily 的 ETF 日线，Phase 1 引入 baostock 后补齐指数。
    """
    q = text(
        """
        SELECT trade_date, open, high, low, close, volume, amount, pct_chg
        FROM etf_daily
        WHERE UPPER(code) = :code AND trade_date BETWEEN :start AND :end
        ORDER BY trade_date
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"code": code.upper(), "start": start, "end": end, "limit": limit})
    return [
        {
            "date": str(r.trade_date),
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
            "amount": r.amount,
            "pct_chg": r.pct_chg,
        }
        for r in rows
    ]


@_cached("stock_search")
async def search_stock(db: AsyncSession, query: str, limit: int = 20) -> list[dict]:
    """股票搜索（按代码或名称模糊匹配）。"""
    q = text(
        """
        SELECT code, name, type, status
        FROM stock_basic
        WHERE UPPER(code) LIKE UPPER(:query) OR name LIKE :query
        ORDER BY code
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"query": f"%{query}%", "limit": limit})
    return [{"code": r.code, "name": r.name, "type": r.type, "status": r.status} for r in rows]


@_cached("stock_valuation")
async def get_stock_valuation(db: AsyncSession, code: str, limit: int = 2000) -> list[dict]:
    """个股估值时间序列（PE/PB/PS）。"""
    q = text(
        """
        SELECT trade_date, pe_ttm, pb_mrq, ps_ttm
        FROM stock_daily
        WHERE UPPER(code) = :code AND pe_ttm IS NOT NULL
        ORDER BY trade_date DESC
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"code": code.upper(), "limit": limit})
    return [
        {"date": str(r.trade_date), "pe_ttm": r.pe_ttm, "pb_mrq": r.pb_mrq, "ps_ttm": r.ps_ttm}
        for r in rows
    ]


@_cached("market_pe_distribution")
async def get_market_pe_distribution(
    db: AsyncSession, trade_date: date, bins: int = 40
) -> dict:
    """全市场 PE 分布（某日快照，真实 stock_daily.pe_ttm）。

    返回中位数/90 分位 + 直方图分箱（供 PE 分布可视化）。
    """
    q = text(
        """
        SELECT pe_ttm
        FROM stock_daily
        WHERE trade_date = :d AND pe_ttm IS NOT NULL
        """
    )
    rows = await db.execute(q, {"d": trade_date})
    pes = [r[0] for r in rows]
    if not pes:
        return {"date": str(trade_date), "count": 0, "median": None, "p90": None, "bins": []}
    pes_sorted = sorted(pes)
    n = len(pes_sorted)
    median = pes_sorted[(n - 1) // 2]
    p90 = pes_sorted[int(n * 0.9) - 1]
    # 分箱：负 PE 单独一桶（亏损股），正 PE 封顶到 CAP 后等宽分桶。
    # 右偏分布若按真实 max 等宽（如 PE=30000），几乎全部股票挤进第一个桶，
    # 直方图退化成「一根柱子」；封顶到 300 后 0-300 区间才有分辨率，
    # PE>300 的极端值并入最后一桶（数量守恒，不丢样本）。
    neg = [p for p in pes_sorted if p <= 0]
    pos = [p for p in pes_sorted if p > 0]
    out_bins: list[dict] = [{"lo": None, "hi": 0, "count": len(neg)}]
    if pos:
        CAP = 300.0
        width = CAP / bins
        counts = [0] * bins
        for p in pos:
            idx = int(min(p, CAP) / width)
            if idx >= bins:
                idx = bins - 1
            counts[idx] += 1
        for i in range(bins):
            out_bins.append(
                {
                    "lo": round(i * width, 1),
                    "hi": round((i + 1) * width, 1),
                    "count": counts[i],
                }
            )
    return {
        "date": str(trade_date),
        "count": n,
        "median": round(median, 2),
        "p90": round(p90, 2),
        "bins": out_bins,
    }


@_cached("macro_indicator")
async def get_macro_indicator(
    db: AsyncSession, indicator: str, start: date, end: date, limit: int = 5000
) -> list[dict]:
    """宏观指标时间序列。"""
    q = text(
        """
        SELECT report_date, field_name, value, unit
        FROM macro_indicator
        WHERE indicator = :indicator AND report_date BETWEEN :start AND :end
        ORDER BY report_date
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"indicator": indicator, "start": start, "end": end, "limit": limit})
    return [
        {"date": str(r.report_date), "field": r.field_name, "value": r.value, "unit": r.unit}
        for r in rows
    ]


async def list_macro_indicators(db: AsyncSession) -> list[str]:
    """可用的宏观指标列表。"""
    q = text("SELECT DISTINCT indicator FROM macro_indicator ORDER BY indicator")
    rows = await db.execute(q)
    return [r[0] for r in rows]


async def list_indices(db: AsyncSession, index_type: str = "index", limit: int = 100) -> list[dict]:
    """指数/ETF 清单（stock_index 元数据表）。"""
    q = text(
        """
        SELECT code, name, type
        FROM stock_index
        WHERE (:type = 'all' OR type = :type)
        ORDER BY code
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"type": index_type, "limit": limit})
    return [{"code": r.code, "name": r.name, "type": r.type} for r in rows]


async def list_factors(
    db: AsyncSession, status: str = "active", category: str = "", limit: int = 50, order_by: str = "ic"
) -> list[dict]:
    """因子库列表（Qlib 因子库真实数据）。

    order_by: ic / icir / rank_ic / turnover
    """
    order_map = {
        "ic": "ic DESC",
        "icir": "icir DESC",
        "rank_ic": "rank_ic DESC",
        "turnover": "turnover ASC",
    }
    order_sql = order_map.get(order_by, "ic DESC")
    cat_cond = "AND category = :category" if category else ""
    q = text(
        f"""
        SELECT name, expression, category, ic, rank_ic, icir, ir, turnover,
               eval_start, eval_end, status
        FROM factor
        WHERE (:status = 'all' OR status = :status) {cat_cond}
        ORDER BY {order_sql}
        LIMIT :limit
        """
    )
    rows = await db.execute(
        q, {"status": status, "category": category or None, "limit": limit}
    )
    return [
        {
            "name": r.name,
            "expression": r.expression,
            "category": r.category,
            "ic": r.ic,
            "rank_ic": r.rank_ic,
            "icir": r.icir,
            "ir": r.ir,
            "turnover": r.turnover,
            "eval_start": r.eval_start,
            "eval_end": r.eval_end,
            "status": r.status,
        }
        for r in rows
    ]


async def factor_summary(db: AsyncSession) -> dict:
    """因子库统计（真实计数）。"""
    q = text(
        """
        SELECT status, COUNT(*) FROM factor GROUP BY status
        """
    )
    rows = await db.execute(q)
    by_status = {r.status: r[1] for r in rows}
    q2 = text("SELECT DISTINCT category FROM factor ORDER BY category")
    cats = await db.execute(q2)
    return {
        "total": sum(by_status.values()),
        "active": by_status.get("active", 0),
        "categories": [r[0] for r in cats],
        "by_status": by_status,
    }


@_cached("ic_distribution")
async def get_factor_ic_distribution(db: AsyncSession, bins: int = 30) -> dict:
    """161 个真实因子的 IC 分布直方图。

    基于 factor 表的聚合 IC（全市场、全历史评估区间），统计分布形态。
    """
    q = text("SELECT ic FROM factor WHERE ic IS NOT NULL")
    rows = await db.execute(q)
    ics = [r[0] for r in rows]
    if not ics:
        return {"count": 0, "bins": [], "median": None, "mean": None, "p90": None}
    ics_sorted = sorted(ics)
    n = len(ics_sorted)
    lo = min(ics_sorted)
    hi = max(ics_sorted)
    if hi == lo:
        # 全部 IC 相等：width=0 会除零，直接单桶返回
        return {
            "count": n,
            "lo": round(lo, 4),
            "hi": round(hi, 4),
            "median": round(lo, 4),
            "mean": round(lo, 4),
            "p90": round(lo, 4),
            "bins": [{"center": round(lo, 4), "count": n}],
        }
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in ics_sorted:
        idx = int((v - lo) / width)
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1
    centers = [round(lo + width * (i + 0.5), 4) for i in range(bins)]
    return {
        "count": n,
        "lo": round(lo, 4),
        "hi": round(hi, 4),
        "median": round(ics_sorted[(n - 1) // 2], 4),
        "mean": round(sum(ics) / n, 4),
        "p90": round(ics_sorted[int(n * 0.9) - 1], 4),
        "bins": [{"center": centers[i], "count": counts[i]} for i in range(bins)],
    }


@_cached("month_end_snapshot")
async def _month_end_snapshot(db: AsyncSession, start: date, end: date) -> list[tuple]:
    """每月末日全市场 PE + 下月前向收益（窗口函数版，避免全量扫描）。

    返回 [(ym, code, pe_ttm, fwd_ret)]，fwd_ret 为月末收盘到下月末收盘的
    「下月前向收益」（LEAD，区间最后一个月的月末快照无前向收益而被剔除）。

    该函数是 get_pe_layers / get_pe_ic / get_factor_ic_scatter / get_layer_nav
    四个热点查询的共同基础数据，缓存后四个接口共享同一份月末快照，避免重复全市场扫描。
    """
    q = text(
        """
        WITH me AS (
          SELECT date_trunc('month', trade_date) AS ym, MAX(trade_date) AS d,
                 row_number() OVER (ORDER BY date_trunc('month', trade_date)) AS mi
          FROM stock_daily
          WHERE trade_date BETWEEN :start AND :end
          GROUP BY 1
        ),
        snap AS (
          SELECT me.mi, me.ym, sd.code, sd.pe_ttm, sd.close
          FROM me JOIN stock_daily sd ON sd.trade_date = me.d AND sd.pe_ttm IS NOT NULL
        ),
        fwd AS (
          SELECT mi, ym, code, pe_ttm,
                 close / LEAD(close) OVER (PARTITION BY code ORDER BY mi) - 1 AS fwd_ret
          FROM snap
        )
        SELECT ym, code, pe_ttm, fwd_ret FROM fwd WHERE fwd_ret IS NOT NULL
        """
    )
    rows = await db.execute(q, {"start": start, "end": end})
    return [(r[0], r[1], r[2], r[3]) for r in rows]


@_cached("pe_layers")
async def get_pe_layers(db: AsyncSession, start: date, end: date, n_groups: int = 5) -> dict:
    """全市场 PE 分层收益热力图（真实数据）。

    每月末日按 PE 从低到高分成 n_groups 组，计算每组下月平均收益。
    返回 {dates: [ym...], groups: [组名], matrix: [[month][group]]}。
    """
    data = await _month_end_snapshot(db, start, end)
    if not data:
        return {"dates": [], "groups": [], "matrix": [], "count": 0}
    by_month: dict[str, list[tuple]] = {}
    for ym, code, pe, fwd in data:
        key = str(ym)[:10]
        by_month.setdefault(key, []).append((pe, fwd))
    dates = sorted(by_month)
    groups = [f"Q{i+1}（低估值）" if i == 0 else (f"Q{i+1}（高估值）" if i == n_groups - 1 else f"Q{i+1}") for i in range(n_groups)]
    matrix: list[list[float | None]] = []
    counts: list[list[int]] = []
    for m in dates:
        pairs = sorted(by_month[m], key=lambda x: x[0])
        n = len(pairs)
        # 按组数分桶，尽量等分（不足时组数 = min(n_groups, n)）
        g = min(n_groups, n)
        row: list[float | None] = []
        cnt: list[int] = []
        for i in range(n_groups):
            if i >= g:
                row.append(None)
                cnt.append(0)
                continue
            lo_i = (i * n) // n_groups
            hi_i = ((i + 1) * n) // n_groups
            if hi_i <= lo_i:
                row.append(None)
                cnt.append(0)
                continue
            sub = pairs[lo_i:hi_i]
            row.append(round(sum(x[1] for x in sub) / len(sub), 4))
            cnt.append(len(sub))
        matrix.append(row)
        counts.append(cnt)
    return {"dates": dates, "groups": groups, "matrix": matrix, "counts": counts, "n_groups": n_groups}


@_cached("pe_ic")
async def get_pe_ic(db: AsyncSession, start: date, end: date) -> dict:
    """PE 因子月度 rank IC 序列（真实数据）。

    每月末日横截面：PE 与下月收益的 Spearman 秩相关。
    """
    data = await _month_end_snapshot(db, start, end)
    if not data:
        return {"dates": [], "ic": [], "mean": None, "std": None, "icir": None}
    by_month: dict[str, list[tuple]] = {}
    for ym, code, pe, fwd in data:
        key = str(ym)[:10]
        by_month.setdefault(key, []).append((pe, fwd))
    dates = sorted(by_month)
    ics: list[float] = []
    ic_dates: list[str] = []  # 与 ics 一一对应（只含样本充足、成功算出 IC 的月份）
    for m in dates:
        pairs = by_month[m]
        if len(pairs) < 30:
            continue
        pes, fwds = zip(*pairs)
        n = len(pes)
        # Spearman：对两者分别排秩
        def ranks(vals):
            idx = sorted(range(n), key=lambda i: vals[i])
            r = [0.0] * n
            for pos, i in enumerate(idx):
                r[i] = pos + 1
            return r

        rp, rf = ranks(pes), ranks(fwds)
        mp = sum(rp) / n
        mf = sum(rf) / n
        cov = sum((a - mp) * (b - mf) for a, b in zip(rp, rf)) / n
        sp = (sum((a - mp) ** 2 for a in rp) / n) ** 0.5
        sf = (sum((a - mf) ** 2 for a in rf) / n) ** 0.5
        if sp == 0 or sf == 0:
            continue
        ics.append(cov / (sp * sf))
        ic_dates.append(m)
    if not ics:
        return {"dates": [], "ic": [], "mean": None, "std": None, "icir": None}
    mean_ic = sum(ics) / len(ics)
    std_ic = (sum((x - mean_ic) ** 2 for x in ics) / (len(ics) - 1)) ** 0.5
    return {
        "dates": ic_dates,
        "ic": [round(x, 4) for x in ics],
        "mean": round(mean_ic, 4),
        "std": round(std_ic, 4),
        "icir": round(mean_ic / std_ic, 4) if std_ic > 0 else None,
        "n_obs": len(ics),
    }


@_cached("industry_pe")
async def get_industry_pe(db: AsyncSession, trade_date: date, min_stocks: int = 30) -> dict:
    """行业 PE 中位数对比（真实数据）。

    某一交易日，按申万一级行业聚合 PE 中位数（行业内市值差异小，比全市场更能反映估值结构）。
    返回 {date, count, industries: [{industry, n, median, lo, hi}]}。
    """
    q = text(
        """
        SELECT si.industry, COUNT(*) AS n,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sd.pe_ttm) AS med,
               MIN(sd.pe_ttm) AS lo, MAX(sd.pe_ttm) AS hi
        FROM stock_industry si
        JOIN stock_daily sd ON UPPER(si.code) = sd.code AND sd.trade_date = :d AND sd.pe_ttm IS NOT NULL
        WHERE si.industry <> ''
        GROUP BY si.industry
        HAVING COUNT(*) >= :min_stocks
        ORDER BY med
        """
    )
    rows = await db.execute(q, {"d": trade_date, "min_stocks": min_stocks})
    industries = [
        {
            "industry": r.industry,
            "n": r.n,
            "median": round(r.med, 2) if r.med is not None else None,
            "lo": round(r.lo, 2) if r.lo is not None else None,
            "hi": round(r.hi, 2) if r.hi is not None else None,
        }
        for r in rows
    ]
    return {"date": str(trade_date), "count": len(industries), "industries": industries}


@_cached("backtest_results")
async def get_backtest_results(db: AsyncSession, limit: int = 20) -> list[dict]:
    """多因子回测结果（真实数据）。

    返回最近 limit 条含净值曲线的回测，解析 nav_curve JSON。
    """
    q = text(
        """
        SELECT id, combination_method, benchmark, topk, n_drop, rebalance_freq,
               annual_return, annual_volatility, sharpe, max_drawdown, excess_return,
               nav_curve, created_at
        FROM backtest_result
        WHERE nav_curve IS NOT NULL AND is_deleted = 0
        ORDER BY id DESC
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"limit": limit})
    out = []
    for r in rows:
        nav = None
        try:
            import json

            parsed = json.loads(r.nav_curve)
            nav = {
                "dates": parsed.get("dates", []),
                "portfolio": parsed.get("portfolio", []),
                "benchmark": parsed.get("benchmark", []),
            }
        except Exception:  # noqa: BLE001
            nav = None
        out.append(
            {
                "id": r.id,
                "combination_method": r.combination_method,
                "benchmark": r.benchmark,
                "topk": r.topk,
                "n_drop": r.n_drop,
                "rebalance_freq": r.rebalance_freq,
                "annual_return": r.annual_return,
                "annual_volatility": r.annual_volatility,
                "sharpe": r.sharpe,
                "max_drawdown": r.max_drawdown,
                "excess_return": r.excess_return,
                "nav": nav,
            }
        )
    return out


@_cached("ic_scatter")
async def get_factor_ic_scatter(db: AsyncSession, start: date, end: date, max_points: int = 8000) -> dict:
    """PE 因子 IC 散点（真实数据）：每月末各股票 PE 百分位 vs 下月收益。

    复用 _month_end_snapshot 的月末快照，返回 {dates, points: [{x, y}], n}。
    x = 当月 PE 在全市场横截面的百分位（0~1，PE 越低百分位越低），
    y = 该股票下月收益。散点整体趋势的斜率即 PE 因子方向。
    """
    data = await _month_end_snapshot(db, start, end)
    # 按月份分组，组内算 PE 百分位
    from collections import defaultdict

    by_month: dict[str, list[tuple]] = defaultdict(list)
    for ym, code, pe, fwd in data:
        by_month[str(ym)[:10]].append((pe, fwd))
    points: list[dict] = []
    dates: list[str] = []
    for m in sorted(by_month):
        pairs = by_month[m]
        if len(pairs) < 30:
            continue
        sorted_pe = sorted(p[0] for p in pairs)
        n = len(sorted_pe)
        for pe, fwd in pairs:
            # 该股票 PE 在当月横截面的百分位（低估值 → 低百分位）
            import bisect

            rank = bisect.bisect_left(sorted_pe, pe)
            pct = rank / n
            points.append({"x": round(pct, 4), "y": round(fwd * 100, 3), "date": m})
        dates.append(m)
    # 采样上限，避免前端一次渲染过多点
    if len(points) > max_points:
        step = len(points) / max_points
        points = [points[int(i * step)] for i in range(max_points)]
    return {"dates": dates, "points": points, "n": len(points), "n_months": len(dates)}


@_cached("layer_nav")
async def get_layer_nav(db: AsyncSession, start: date, end: date, n_groups: int = 5) -> dict:
    """PE 分层累计净值（真实数据）：每月末按 PE 分 Q1~Q5，各组逐月累乘净值。

    返回 {dates, groups, nav: [[Q1净值...], ...], n_groups}。
    与 pe-layers 热力图同源（同快照同分组），但以净值曲线呈现单调性。
    """
    data = await _month_end_snapshot(db, start, end)
    if not data:
        return {"dates": [], "groups": [], "nav": [], "n_groups": n_groups}
    from collections import defaultdict

    by_month: dict[str, list[tuple]] = defaultdict(list)
    for ym, code, pe, fwd in data:
        by_month[str(ym)[:10]].append((pe, fwd))
    dates = sorted(by_month)
    groups = [f"Q{i+1}（低估值）" if i == 0 else (f"Q{i+1}（高估值）" if i == n_groups - 1 else f"Q{i+1}") for i in range(n_groups)]
    # nav[g][t]：第 g 组到第 t 个月的累计净值（起点 1.0，不包含首个快照月）
    nav = [[1.0] for _ in range(n_groups)]
    for m in dates:
        pairs = sorted(by_month[m], key=lambda x: x[0])
        n = len(pairs)
        g = min(n_groups, n)
        for i in range(n_groups):
            if i >= g:
                nav[i].append(nav[i][-1])
                continue
            lo_i = (i * n) // n_groups
            hi_i = ((i + 1) * n) // n_groups
            if hi_i <= lo_i:
                nav[i].append(nav[i][-1])
                continue
            sub = pairs[lo_i:hi_i]
            avg_ret = sum(x[1] for x in sub) / len(sub)
            nav[i].append(nav[i][-1] * (1 + avg_ret))
    return {"dates": dates, "groups": groups, "nav": nav, "n_groups": n_groups}


@_cached("factor_ic_turnover")
async def get_factor_ic_turnover(db: AsyncSession, status: str = "active", limit: int = 200) -> dict:
    """因子 IC vs 换手散点（真实数据）：factor 表全部因子的 IC 与换手率。

    返回 {points: [{name, ic, rank_ic, icir, turnover, category}], n}。
    揭示「高换手因子的 IC 未必更高」——换手高的因子交易成本侵蚀更大。
    """
    q = text(
        """
        SELECT name, ic, rank_ic, icir, turnover, category
        FROM factor
        WHERE (:status = 'all' OR status = :status)
          AND ic IS NOT NULL AND turnover IS NOT NULL
        ORDER BY ic DESC
        LIMIT :limit
        """
    )
    rows = await db.execute(q, {"status": status, "limit": limit})
    points = [
        {
            "name": r.name,
            "ic": round(float(r.ic), 4),
            "rank_ic": round(float(r.rank_ic), 4) if r.rank_ic is not None else None,
            "icir": round(float(r.icir), 4) if r.icir is not None else None,
            "turnover": round(float(r.turnover), 4),
            "category": r.category or "",
        }
        for r in rows
    ]
    return {"points": points, "n": len(points)}
