import asyncio

from langgraph.constants import START, END
from langgraph.graph import StateGraph

from app.agent.context import DataAgentContext
from app.agent.nodes.add_context import add_context
from app.agent.nodes.column_recall import column_recall
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.execute_sql import execute_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric_info import filter_metric_info
from app.agent.nodes.filter_table_info import filter_table_info
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.metric_recall import metric_recall
from app.agent.nodes.validate_sql import validate_sql
from app.agent.nodes.value_recall import value_recall
from app.agent.state import DataAgentState
from app.clients.embedding_client import embedding_client_manager
from app.clients.es_client import es_client_manager
from app.clients.mysql_client import meta_client_manager, dw_client_manager
from app.clients.qdrant_client import qdrant_client_manager
from app.core.context import request_id_ctx_var
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository
from app.repositories.qdrant.metric_repository_qdrant import MetricQdrantRepository

graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

graph_builder.add_node("extract_keywords", extract_keywords)
graph_builder.add_node("column_recall", column_recall)
graph_builder.add_node("value_recall", value_recall)
graph_builder.add_node("metric_recall", metric_recall)
graph_builder.add_node("merge_retrieved_info", merge_retrieved_info)
graph_builder.add_node("filter_table_info", filter_table_info)
graph_builder.add_node("filter_metric_info", filter_metric_info)
graph_builder.add_node("add_context", add_context)
graph_builder.add_node("generate_sql", generate_sql)
graph_builder.add_node("validate_sql", validate_sql)
graph_builder.add_node("correct_sql", correct_sql)
graph_builder.add_node("execute_sql", execute_sql)

graph_builder.add_edge(START, "extract_keywords")
graph_builder.add_edge("extract_keywords", "column_recall")
graph_builder.add_edge("extract_keywords", "value_recall")
graph_builder.add_edge("extract_keywords", "metric_recall")
graph_builder.add_edge("value_recall", "merge_retrieved_info")
graph_builder.add_edge("column_recall", "merge_retrieved_info")
graph_builder.add_edge("metric_recall", "merge_retrieved_info")
graph_builder.add_edge("merge_retrieved_info", "filter_table_info")
graph_builder.add_edge("merge_retrieved_info", "filter_metric_info")
graph_builder.add_edge("filter_table_info", "add_context")
graph_builder.add_edge("filter_metric_info", "add_context")
graph_builder.add_edge("add_context", "generate_sql")
graph_builder.add_edge("generate_sql", "validate_sql")
graph_builder.add_edge("validate_sql", "execute_sql")
graph_builder.add_conditional_edges("validate_sql",
                                    lambda state: "execute_sql" if state["error"] is None else "correct_sql")
graph_builder.add_edge("execute_sql", END)
graph = graph_builder.compile()


async def main():
    request_id_ctx_var.set("1")
    state = DataAgentState(query="统计一下2025年1月份各品类的销售额占比")

    qdrant_client_manager.init()
    column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
    metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)

    embedding_client_manager.init()
    embedding_client = embedding_client_manager.client

    es_client_manager.init()
    value_es_repository = ValueESRepository(es_client_manager.client)

    meta_client_manager.init()
    dw_client_manager.init()
    async with (meta_client_manager.session_factory() as meta_session,
                dw_client_manager.session_factory() as dw_session):
        meta_mysql_repository = MetaMySQLRepository(meta_session)
        dw_mysql_repository = DWMySQLRepository(dw_session)
        context = DataAgentContext(
            metric_qdrant_repository=metric_qdrant_repository,
            value_es_repository=value_es_repository,
            column_qdrant_repository=column_qdrant_repository,
            embedding_client=embedding_client,
            meta_mysql_repository=meta_mysql_repository,
            dw_mysql_repository=dw_mysql_repository)

        async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
            print(chunk)


if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
