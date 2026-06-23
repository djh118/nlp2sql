from app.clients.embedding_client import embedding_client_manager
from app.clients.qdrant_client import qdrant_client_manager
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.repositories.qdrant.base_repository_qdrant import BaseQdrantRepository


class ColumnQdrantRepository(BaseQdrantRepository[ColumnInfoQdrant]):
    collection_name = "data_agent_column"


if __name__ == '__main__':
    import asyncio


    async def test():
        embedding_client_manager.init()
        embedding_client = embedding_client_manager.client

        qdrant_client_manager.init()
        vector_repository = ColumnQdrantRepository(qdrant_client_manager.client)

        query = "统计一下东北地区的订单数量"
        result = await vector_repository.search(embedding_client.embed_query(query))
        print(result[0]["description"])


    asyncio.run(test())
