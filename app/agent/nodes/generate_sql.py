from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import invoke_sql_llm_with_fallback
from app.agent.state import DataAgentState
from app.core.fault_tolerance.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
from app.core.fault_tolerance.sql_guard import guard_sql, sanitize_sql
from app.core.logging import logger
from app.prompt.prompt_loader import load_prompt
from app.config.app_config import app_config


async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "生成SQL"})

    table_infos = state["table_infos"]
    metric_infos = state["metric_infos"]
    date_info = state["date_info"]
    db_info = state["db_info"]
    query = state["query"]

    try:
        cb_config = CircuitBreakerConfig(
            failure_threshold=app_config.fault_tolerance.circuit_breaker.llm_call.failure_threshold,
            recovery_timeout=app_config.fault_tolerance.circuit_breaker.llm_call.recovery_timeout,
        )
        cb = get_circuit_breaker("llm_call", cb_config)
        sql = await cb.call(
            _do_generate_sql, table_infos, metric_infos, date_info, db_info, query
        )
        sql = sanitize_sql(sql)

        is_safe, guard_msg = guard_sql(
            sql,
            block_select_star=app_config.fault_tolerance.sql_guard.block_select_star,
            block_no_where=app_config.fault_tolerance.sql_guard.block_no_where,
        )
        if not is_safe:
            logger.warning(f"SQL被拦截: {guard_msg}")
            writer({"stage": "SQL安全拦截"})
            return {"sql": "", "error": guard_msg, "error_category": "sql_guard"}

        logger.info(f"生成SQL: {sql}")
        return {"sql": sql}
    except Exception as e:
        logger.error(f"生成SQL失败: {e}")
        return {"sql": "", "error": f"SQL生成失败: {str(e)}"}


async def _do_generate_sql(table_infos, metric_infos, date_info, db_info, query):
    prompt = PromptTemplate(
        template=load_prompt("generate_sql"),
        input_variables=["table_infos", "metric_infos", "date_info", "db_info"],
    )
    result = await invoke_sql_llm_with_fallback(
        prompt,
        {
            "table_infos": table_infos,
            "metric_infos": metric_infos,
            "date_info": date_info,
            "db_info": db_info,
            "query": query,
        },
        timeout=app_config.fault_tolerance.query_timeout.llm_invoke,
    )
    return result
