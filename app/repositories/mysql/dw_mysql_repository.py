import asyncio
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.app_config import app_config
from app.core.fault_tolerance.cache_manager import sql_cache_key, get_cache_manager
from app.core.logging import logger


class DWMySQLRepository:
    def __init__(self, dw_session: AsyncSession):
        self.dw_session = dw_session

    async def _get_connection_id(self) -> int:
        result = await self.dw_session.execute(text("SELECT CONNECTION_ID() as conn_id"))
        return result.scalar()

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        sql = text(f"show columns from {table_name}")
        result = await self.dw_session.execute(sql)
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(self, table_name: str, column_name: str, limit: int) -> list[Any]:
        sql = text(f"""
            select {column_name} as column_value
            from {table_name}
            group by {column_name}
            limit {limit}
        """)
        result = await self.dw_session.execute(sql)
        return [row.column_value for row in result.fetchall()]

    async def get_db_info(self) -> dict[str, str]:
        dialect = self.dw_session.get_bind().dialect.name
        sql = text("select version() as version")
        result = await self.dw_session.execute(sql)
        version = result.scalar()
        return {"dialect": dialect, "version": version}

    async def get_date_info(self) -> dict[str, str]:
        sql = text("select now() as now")
        result = await self.dw_session.execute(sql)
        now = result.scalar()
        return {
            "date": now.strftime("%Y-%m-%d"),
            "weekday": now.strftime("%A"),
            "quarter": now.strftime("%Q"),
        }

    async def validate_sql(self, query):
        await self.dw_session.execute(text(f"explain {query}"))

    async def execute_sql(self, sql, timeout=None):
        if timeout is None:
            timeout = app_config.fault_tolerance.query_timeout.sql_execute

        cache_key = sql_cache_key(sql)
        cache = get_cache_manager()
        cached = cache.get(cache_key)
        if cached is not None:
            logger.info(f"[cache] 命中缓存: {sql[:60]}...")
            return cached

        conn_id = await self._get_connection_id()
        try:
            result = await asyncio.wait_for(
                self._do_execute(sql),
                timeout=timeout,
            )
            if await self._should_cache(sql):
                cache.put(cache_key, result)
            return result
        except asyncio.TimeoutError:
            logger.error(f"[timeout] SQL执行超时({timeout}s)，KILL会话 {conn_id}")
            try:
                await self.dw_session.execute(text(f"KILL CONNECTION {conn_id}"))
            except Exception:
                pass
            raise TimeoutError(f"SQL执行超时({timeout}s)，已强制终止")

    async def _do_execute(self, sql):
        result = await self.dw_session.execute(text(sql))
        return [dict(row) for row in result.mappings().fetchall()]

    async def _should_cache(self, sql) -> bool:
        try:
            explain_result = await self.dw_session.execute(text(f"EXPLAIN {sql}"))
            row = explain_result.fetchone()
            if row and hasattr(row, "rows_examined"):
                threshold = app_config.fault_tolerance.cache.slow_query_threshold_ms
                return int(row.rows_examined) > threshold
        except Exception:
            pass
        return False
