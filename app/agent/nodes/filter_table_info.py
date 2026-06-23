from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.logging import logger
from app.prompt.prompt_loader import load_prompt


async def filter_table_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "筛选表信息"})

    table_infos = state["table_infos"]
    query = state["query"]

    try:
        prompt = PromptTemplate(template=load_prompt("filter_table_info"), input_variables=["query", "table_infos"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query, "table_infos": table_infos})
        for table_info in table_infos[:]:
            if table_info['name'] not in result:
                table_infos.remove(table_info)
            else:
                for column in table_info['columns'][:]:
                    if column['name'] not in result[table_info['name']]:
                        table_info['columns'].remove(column)

        logger.info(f"表格筛选结果: {[table_info['name'] for table_info in table_infos]}")
        return {"table_infos": table_infos}
    except Exception as e:
        logger.error(f"表格筛选失败: {str(e)}")
        raise
