from app.clients.embedding_client import embedding_client_manager
from app.clients.qdrant_client import qdrant_client_manager
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.repositories.qdrant.base_repository_qdrant import BaseQdrantRepository


class MetricQdrantRepository(BaseQdrantRepository[MetricInfoQdrant]):
    collection_name = "data_agent_metric"


if __name__ == '__main__':
    import asyncio


    async def test():
        embedding_client_manager.init()
        embedding_client = embedding_client_manager.client

        qdrant_client_manager.init()
        metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)

        query = "统计一下销售总额"
        result = await metric_qdrant_repository.search(embedding_client.embed_query(query))
        print(result[0]['name'])


    asyncio.run(test())
