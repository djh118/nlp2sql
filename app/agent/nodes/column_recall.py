from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.logging import logger
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.prompt.prompt_loader import load_prompt
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository


async def column_recall(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    从向量数据库中召回列信息
    """
    writer = runtime.stream_writer
    writer({"stage": "召回字段信息"})

    keywords = state["keywords"]
    query = state["query"]
    column_qdrant_repository: ColumnQdrantRepository = runtime.context['column_qdrant_repository']
    embedding_client: HuggingFaceEndpointEmbeddings = runtime.context['embedding_client']

    try:
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_column_recall"), input_variables=["query"])
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})

        keywords = list(set(keywords + result))

        columns_map: dict[str, ColumnInfoQdrant] = {}
        for keyword in keywords:
            embedding = await embedding_client.aembed_query(keyword)
            columns: list[ColumnInfoQdrant] = await column_qdrant_repository.search(embedding, 0.6, 5)
            for column in columns:
                if column["id"] not in columns_map:
                    columns_map[column["id"]] = column

        retrieved_columns = columns_map.values()

        logger.info(f"字段信息召回成功: {columns_map.keys()}")

        return {"retrieved_columns": list(retrieved_columns)}
    except Exception as e:
        logger.error(f"字段信息召回失败: {str(e)}")
        raise
