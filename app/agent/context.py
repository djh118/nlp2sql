from typing import TypedDict

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository
from app.repositories.qdrant.metric_repository_qdrant import MetricQdrantRepository


class DataAgentContext(TypedDict):
    metric_qdrant_repository: MetricQdrantRepository  # 指标向量库
    column_qdrant_repository: ColumnQdrantRepository  # 字段向量库
    value_es_repository: ValueESRepository  # 字段值全文检索库
    embedding_client: HuggingFaceEndpointEmbeddings  # 向量服务客户端
    meta_mysql_repository: MetaMySQLRepository  # 元数据MySQL库
    dw_mysql_repository: DWMySQLRepository  # 数据仓库MySQL库
