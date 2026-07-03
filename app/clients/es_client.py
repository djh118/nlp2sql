from elasticsearch import AsyncElasticsearch

from app.config.app_config import ESConfig, app_config


class ESClientManager:
    def __init__(self, config: ESConfig):
        self.config = config
        self.client: AsyncElasticsearch | None = None

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.client = AsyncElasticsearch(
            hosts=[self._get_url()],
            request_timeout=app_config.fault_tolerance.query_timeout.es_search,
            max_retries=1,
            retry_on_timeout=True,
        )

    async def close(self):
        await self.client.close()


es_client_manager = ESClientManager(app_config.es)
