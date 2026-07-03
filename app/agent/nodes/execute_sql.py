from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.fault_tolerance.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
from app.core.fault_tolerance.fallback_registry import FallbackRegistry
from app.core.logging import logger
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository
from app.config.app_config import app_config


async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "执行SQL语句"})

    sql = state["sql"]
    dw_mysql_repository: DWMySQLRepository = runtime.context["dw_mysql_repository"]

    try:
        cb_config = CircuitBreakerConfig(
            failure_threshold=app_config.fault_tolerance.circuit_breaker.sql_execution.failure_threshold,
            recovery_timeout=app_config.fault_tolerance.circuit_breaker.sql_execution.recovery_timeout,
        )
        cb = get_circuit_breaker("sql_execution", cb_config)
        result = await cb.call(dw_mysql_repository.execute_sql, sql)
        logger.info(f"SQL执行结果: {result}")
        writer({"result": result})
    except Exception as e:
        logger.error(f"SQL执行失败: {e}")
        writer({"error": FallbackRegistry.db_unavailable_message()})
