from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.logging import logger
from app.prompt.prompt_loader import load_prompt


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

    try:
        prompt = PromptTemplate(template=load_prompt("correct_sql"),
                                input_variables=["query", "sql", "error", "table_infos", "metric_infos", "date_info",
                                                 "db_info"])
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke(
            {"query": query, "sql": sql, "error": error, "table_infos": table_infos, "metric_infos": metric_infos,
             "date_info": date_info, "db_info": db_info})
        logger.info(f'校正SQL结果：{result}')
        return {"sql": result}
    except Exception as e:
        logger.error(f'校正SQL失败：{e}')
        raise
