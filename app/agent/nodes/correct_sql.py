from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import invoke_llm_with_fallback
from app.agent.state import DataAgentState
from app.core.logging import logger
from app.prompt.prompt_loader import load_prompt
from app.config.app_config import app_config
from app.core.fault_tolerance.sql_guard import sanitize_sql


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "校正SQL"})

    query = state["query"]
    sql = state["sql"]
    error = state["error"]
    table_infos = state["table_infos"]
    metric_infos = state["metric_infos"]
    date_info = state["date_info"]
    db_info = state["db_info"]

    retry_count = state.get("sql_retry_count", 0) + 1
    max_retry = app_config.fault_tolerance.sql_guard.max_retry_count

    if retry_count > max_retry:
        logger.error(f"SQL修正已达最大次数({max_retry})，终止")
        return {"error": f"SQL修正失败已达上限({max_retry}次)，请尝试重新描述查询"}

    clean_sql = sanitize_sql(sql)
    clean_error = sanitize_sql(error)[:500] if error else ""

    try:
        prompt = PromptTemplate(
            template=load_prompt("correct_sql"),
            input_variables=[
                "query", "sql", "error", "table_infos",
                "metric_infos", "date_info", "db_info",
            ],
        )
        result = await invoke_llm_with_fallback(
            prompt,
            {
                "query": query,
                "sql": clean_sql,
                "error": clean_error,
                "table_infos": table_infos,
                "metric_infos": metric_infos,
                "date_info": date_info,
                "db_info": db_info,
            },
            timeout=app_config.fault_tolerance.query_timeout.llm_invoke,
        )
        logger.info(f"校正SQL结果: {result}")
        return {"sql": result, "sql_retry_count": retry_count}
    except Exception as e:
        logger.error(f"校正SQL失败: {e}")
        return {"error": f"SQL修正失败: {str(e)}", "sql_retry_count": retry_count}
