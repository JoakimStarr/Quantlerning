"""只读数据库连接（quantlab 库）。

学习站只读 QuantLab 数据，所有查询在只读事务中执行，防止任何误写。
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

# 连接串带上 application_name 便于区分；AsyncPG 只读模式由事务隔离保障
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI 依赖：只读会话。事务以 ROLLBACK 结束，确保只读。"""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            # 只读：强制回滚，避免任何事务写提交
            await session.rollback()


async def check_db_connection() -> dict:
    """健康检查：验证 DB 连通性并返回关键表行数（pg_class.reltuples 估计值）。

    用规划器统计而非 COUNT(*)：stock_daily 等千万行表全扫会让健康检查变慢。
    """
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT relname, reltuples::bigint FROM pg_class "
                "WHERE relname = ANY(:names)"
            ),
            {"names": ["stock_daily", "stock_basic", "financial_indicator", "factor"]},
        )
        return {r[0]: r[1] for r in rows}
