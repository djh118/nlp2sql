from typing import Generic, TypeVar

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from app.config.app_config import app_config

PayloadT = TypeVar("PayloadT")


class BaseQdrantRepository(Generic[PayloadT]):
    collection_name: str

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        exist = await self.client.collection_exists(self.collection_name)
        if not exist:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=app_config.qdrant.embedding_size,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert(
            self,
            ids: list,
            embeddings: list[list[float]],
            payloads: list[PayloadT],
            batch_size: int = 10,
    ):

        zipped = list(zip(ids, embeddings, payloads))
        for i in range(0, len(zipped), batch_size):
            batch = zipped[i:i + batch_size]
            points = [
                PointStruct(id=id, vector=embedding, payload=payload)
                for id, embedding, payload in batch
            ]
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

    async def search(
            self,
            vector: list[float],
            score_threshold: float = 0.6,
            limit: int = 10,
    ) -> list[PayloadT]:
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            score_threshold=score_threshold,
            limit=limit,
        )
        return [point.payload for point in result.points]



