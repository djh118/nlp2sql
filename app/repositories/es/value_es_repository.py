import asyncio

from elasticsearch import AsyncElasticsearch

from app.clients.es_client import es_client_manager
from app.models.es.value_info_es import ValueInfoES


class ValueESRepository:
    es_index_name = "data_agent"
    es_index_mappings = {
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_max_word"},
            "type": {"type": "keyword"},
            "column_id": {"type": "keyword"},
            "column_name": {"type": "keyword"},
            "table_id": {"type": "keyword"},
            "table_name": {"type": "keyword"},
        }
    }

    def __init__(self, es_client: AsyncElasticsearch):
        self.es_client = es_client

    async def ensure_index(self):
        if not await self.es_client.indices.exists(index=self.es_index_name):
            await self.es_client.indices.create(index=self.es_index_name,
                                                mappings=self.es_index_mappings)

    async def batch_index(self, docs: list[ValueInfoES], batch_size: int = 10):

        for i in range(0, len(docs), batch_size):
            batch = docs[i:i + batch_size]
            operations = []

            for doc in batch:
                operations.append({
                    "index": {
                        "_index": self.es_index_name,
                        "_id": doc["id"]
                    }
                })
                operations.append(doc)

            await self.es_client.bulk(operations=operations)

    async def query(self, query: str, score_threshold: float = 0.6, limit: int = 10) -> list[ValueInfoES]:

        es_query = {
            "match": {
                "value": query
            }
        }

        resp = await self.es_client.search(
            index=self.es_index_name,
            query=es_query,
            min_score=score_threshold,
            size=limit
        )

        hits = resp.get("hits", {}).get("hits", [])

        results: list[ValueInfoES] = []
        for hit in hits:
            source = hit["_source"]
            results.append(source)

        return results


if __name__ == '__main__':
    async def test():
        es_client_manager.init()
        es_client = es_client_manager.client
        full_text_repository = ValueESRepository(es_client)
        query = "统计一下手机产品的销量"
        print(await full_text_repository.query(query=query))
        await es_client_manager.close()


    asyncio.run(test())
