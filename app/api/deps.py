from fastapi import Depends

from app.agent.graph import graph
from app.clients.embedding_client import embedding_client_manager
from app.clients.mysql_client import dw_client_manager, meta_client_manager
from app.clients.qdrant_client import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository
from app.repositories.qdrant.metric_repository_qdrant import MetricQdrantRepository
from app.service.chat_service import ChatService
from app.clients.es_client import es_client_manager

# 获取 DW 库 Session
async def get_dw_session():
    async with dw_client_manager.session_factory() as session:
        yield session


# 获取 Meta 库 Session
async def get_meta_session():
    async with meta_client_manager.session_factory() as session:
        yield session

# 获取 Meta Repository
async def get_meta_repository(meta_session=Depends(get_meta_session)):
    return MetaMySQLRepository(meta_session)

# 获取 DW Repository
async def get_dw_repository(dw_session=Depends(get_dw_session)):
    return DWMySQLRepository(dw_session)

# 获取 字段 Qdrant Repository
async def get_column_qdrant_repository():
    return ColumnQdrantRepository(qdrant_client_manager.client)

# 获取 指标 Qdrant Repository
async def get_metric_qdrant_repository():
    return MetricQdrantRepository(qdrant_client_manager.client)

# 获取 字段值 ES Repository
async def get_value_es_repository():
    return ValueESRepository(es_client_manager.client)

# 获取 Embedding Client
async def get_embedding_client():
    return embedding_client_manager.client

# 获取 Graph
async def get_graph():
    return graph

# 获取 Chat Service
async def get_chat_service(
        graph=Depends(get_graph),
        meta_repository=Depends(get_meta_repository),
        dw_repository=Depends(get_dw_repository),
        column_qdrant_repository=Depends(get_column_qdrant_repository),
        metric_qdrant_repository=Depends(get_metric_qdrant_repository),
        value_es_repository=Depends(get_value_es_repository),
        embedding_client=Depends(get_embedding_client),
) -> ChatService:
    return ChatService(
        graph=graph,
        meta_mysql_repository=meta_repository,
        dw_mysql_repository=dw_repository,
        column_qdrant_repository=column_qdrant_repository,
        metric_qdrant_repository=metric_qdrant_repository,
        value_es_repository=value_es_repository,
        embedding_client=embedding_client,
    )
