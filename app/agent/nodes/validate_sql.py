from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.logging import logger
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "验证SQL语句"})
    sql = state["sql"]
    dw_mysql_repository: DWMySQLRepository = runtime.context['dw_mysql_repository']

    try:
        await dw_mysql_repository.validate_sql(sql)
        logger.info("SQL校验通过")
        return {"error": None}
    except Exception as e:
        logger.error(f"SQL校验失败: {e}")
        return {"error": str(e)}
