from datetime import datetime

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState, DBInfoState
from app.core.logging import logger


async def add_context(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "添加上下文信息"})
    today = datetime.today()

    quarter = f"Q{(today.month - 1) // 3 + 1}"
    date_info = DateInfoState(
        date=today.strftime("%Y-%m-%d"),
        weekday=today.strftime("%A"),
        quarter=quarter,
    )

    db_info = DBInfoState(**await runtime.context['dw_mysql_repository'].get_db_info())
    logger.info(f'添加上下文信息-date_info:{date_info},db_info:{db_info}')
    return {
        "date_info": date_info,
        "db_info": db_info,
    }
