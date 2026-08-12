"""数据查询路由：只读 quantlab 库。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..services.data import queries

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/search")
async def search(q: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    """股票搜索。"""
    return await queries.search_stock(db, q)


@router.get("/stock/{code}/daily")
async def stock_daily(
    code: str,
    start: date = Query(...),
    end: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """个股日线行情。"""
    return await queries.get_stock_daily(db, code, start, end)


@router.get("/stock/{code}/valuation")
async def stock_valuation(code: str, db: AsyncSession = Depends(get_db)):
    """个股估值序列。"""
    return await queries.get_stock_valuation(db, code)


@router.get("/indices")
async def indices(
    index_type: str = Query("all", pattern="^(all|index|etf)$"),
    db: AsyncSession = Depends(get_db),
):
    """指数/ETF 清单。"""
    return await queries.list_indices(db, index_type)


@router.get("/factors")
async def factors(
    status: str = Query("active", pattern="^(all|active|disabled)$"),
    category: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
    order_by: str = Query("ic", pattern="^(ic|icir|rank_ic|turnover)$"),
    db: AsyncSession = Depends(get_db),
):
    """因子库列表（QuantLab 真实数据）。"""
    return await queries.list_factors(db, status, category, limit, order_by)


@router.get("/factors/summary")
async def factors_summary(db: AsyncSession = Depends(get_db)):
    """因子库统计（真实计数）。"""
    return await queries.factor_summary(db)


@router.get("/factors/ic-distribution")
async def factors_ic_distribution(
    bins: int = Query(30, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
):
    """161 个真实因子的 IC 分布直方图。"""
    return await queries.get_factor_ic_distribution(db, bins)


@router.get("/factors/pe-layers")
async def factors_pe_layers(
    start: date = Query(...),
    end: date = Query(...),
    n_groups: int = Query(5, ge=2, le=10),
    db: AsyncSession = Depends(get_db),
):
    """全市场 PE 分层收益热力图（真实数据）。"""
    return await queries.get_pe_layers(db, start, end, n_groups)


@router.get("/factors/pe-ic")
async def factors_pe_ic(
    start: date = Query(...),
    end: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PE 因子月度 rank IC 序列（真实数据）。"""
    return await queries.get_pe_ic(db, start, end)


@router.get("/factors/industry-pe")
async def factors_industry_pe(
    trade_date: date = Query(...),
    min_stocks: int = Query(30, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
):
    """行业 PE 中位数对比（真实数据）。"""
    return await queries.get_industry_pe(db, trade_date, min_stocks)


@router.get("/backtests")
async def backtests(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """QuantLab 多因子回测结果（真实数据）。"""
    return await queries.get_backtest_results(db, limit)


@router.get("/index/{code}/daily")
async def index_daily(
    code: str,
    start: date = Query(...),
    end: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """指数/ETF 日线行情。"""
    return await queries.get_index_daily(db, code, start, end)


@router.get("/market/pe-distribution")
async def market_pe_distribution(
    trade_date: date = Query(...),
    bins: int = Query(40, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
):
    """全市场 PE 分布快照。"""
    return await queries.get_market_pe_distribution(db, trade_date, bins)


@router.get("/macro/indicators")
async def macro_indicators(db: AsyncSession = Depends(get_db)):
    """宏观指标列表。"""
    return await queries.list_macro_indicators(db)


@router.get("/macro/{indicator}")
async def macro(
    indicator: str,
    start: date = Query(...),
    end: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """宏观指标序列。"""
    return await queries.get_macro_indicator(db, indicator, start, end)
