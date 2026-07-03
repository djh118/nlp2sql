from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.fault_tolerance.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
from app.core.fault_tolerance.fallback_registry import FallbackRegistry
from app.core.logging import logger
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.prompt.prompt_loader import load_prompt
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository
from app.config.app_config import app_config


async def column_recall(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回字段信息"})

    keywords = state["keywords"]
    query = state["query"]
    column_qdrant_repository: ColumnQdrantRepository = runtime.context["column_qdrant_repository"]
    embedding_client: HuggingFaceEndpointEmbeddings = runtime.context["embedding_client"]

    try:
        cb_config = CircuitBreakerConfig(
            failure_threshold=app_config.fault_tolerance.circuit_breaker.vector_retrieval.failure_threshold,
            recovery_timeout=app_config.fault_tolerance.circuit_breaker.vector_retrieval.recovery_timeout,
        )
        cb = get_circuit_breaker("column_recall", cb_config)
        result = await cb.call(_do_column_recall, keywords, query, column_qdrant_repository, embedding_client)
        return result
    except Exception as e:
        logger.warning(f"字段向量检索失败，降级到关键词检索: {e}")
        writer({"stage": "字段召回降级"})
        meta_mysql = runtime.context["meta_mysql_repository"]
        fallback_columns = await FallbackRegistry.vector_retrieval_fallback(query, meta_mysql)
        if not fallback_columns:
            writer({"warning": FallbackRegistry.empty_recall_message()})
        return {"retrieved_columns": fallback_columns}


async def _do_column_recall(keywords, query, column_qdrant_repository, embedding_client):
    prompt = PromptTemplate(
        template=load_prompt("extend_keywords_for_column_recall"), input_variables=["query"]
    )
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
