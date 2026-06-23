from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.logging import logger
from app.models.es.value_info_es import ValueInfoES
from app.prompt.prompt_loader import load_prompt
from app.repositories.es.value_es_repository import ValueESRepository


async def value_recall(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    召回字段值
    """
    writer = runtime.stream_writer
    writer({"stage": "召回字段值"})

    keywords = state["keywords"]
    query = state["query"]
    value_es_repository: ValueESRepository = runtime.context['value_es_repository']

    try:
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"), input_variables=["query"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        result = await chain.ainvoke(input={"query": query})
        keywords = list(set(keywords + result))

        values_map: dict[str, ValueInfoES] = {}
        for keyword in keywords:
            values = await value_es_repository.query(keyword, score_threshold=0.6, limit=5)
            for value in values:
                if value["id"] not in values_map:
                    values_map[value["id"]] = value

        retrieved_values = values_map.values()
        logger.info(f"召回字段值: {values_map.keys()}")
        return {"retrieved_values": retrieved_values}
    except Exception as e:
        logger.error(f"召回字段值失败: {str(e)}")
        raise
