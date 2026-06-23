from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.embedding_client import embedding_client_manager
from app.clients.es_client import es_client_manager
from app.clients.mysql_client import dw_client_manager, meta_client_manager
from app.clients.qdrant_client import qdrant_client_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段
    dw_client_manager.init()
    meta_client_manager.init()
    es_client_manager.init()
    qdrant_client_manager.init()
    embedding_client_manager.init()
    yield
    # 关闭阶段
    await dw_client_manager.close()
    await meta_client_manager.close()
    await es_client_manager.close()
    await qdrant_client_manager.close()

