from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.fault_tolerance.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
from app.core.fault_tolerance.fallback_registry import FallbackRegistry
from app.core.logging import logger
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import load_prompt
from app.repositories.qdrant.metric_repository_qdrant import MetricQdrantRepository
from app.config.app_config import app_config


async def metric_recall(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回指标信息"})

    keywords = state["keywords"]
    query = state["query"]
    embedding_client = runtime.context["embedding_client"]
    metric_qdrant_repository: MetricQdrantRepository = runtime.context["metric_qdrant_repository"]

    try:
        cb_config = CircuitBreakerConfig(
            failure_threshold=app_config.fault_tolerance.circuit_breaker.vector_retrieval.failure_threshold,
            recovery_timeout=app_config.fault_tolerance.circuit_breaker.vector_retrieval.recovery_timeout,
        )
        cb = get_circuit_breaker("metric_recall", cb_config)
        result = await cb.call(_do_metric_recall, keywords, query, embedding_client, metric_qdrant_repository)
        return result
    except Exception as e:
        logger.warning(f"指标向量检索失败，降级: {e}")
        writer({"stage": "指标召回降级"})
        return {"retrieved_metrics": []}


async def _do_metric_recall(keywords, query, embedding_client, metric_qdrant_repository):
    prompt = PromptTemplate(
        template=load_prompt("extend_keywords_for_metric_recall"), input_variables=["query"]
    )
    output_parser = JsonOutputParser()
    chain = prompt | llm | output_parser
    result = chain.invoke(input={"query": query})
    keywords = list(set(keywords + result))

    metrics_map: dict[str, MetricInfoQdrant] = {}
    for keyword in keywords:
        embedding = await embedding_client.aembed_query(keyword)
        metrics = await metric_qdrant_repository.search(embedding, score_threshold=0.6, limit=5)
        for metric in metrics:
            if metric["id"] not in metrics_map:
                metrics_map[metric["id"]] = metric

    retrieved_metrics = metrics_map.values()
    logger.info(f"召回指标信息: {metrics_map.keys()}")
    return {"retrieved_metrics": retrieved_metrics}
