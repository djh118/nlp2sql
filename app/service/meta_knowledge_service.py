import uuid

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.config.config_loader import load_config
from app.config.meta_config import MetaConfig, TableConfig, MetricConfig
from app.core.logging import logger
from app.models.es.value_info_es import ValueInfoES
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_repository_qdrant import ColumnQdrantRepository
from app.repositories.qdrant.metric_repository_qdrant import MetricQdrantRepository


class MetaKnowledgeService:

    def __init__(self,
                 dw_mysql_repository: DWMySQLRepository,
                 meta_mysql_repository: MetaMySQLRepository,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 column_qdrant_repository: ColumnQdrantRepository,
                 metric_qdrant_repository: MetricQdrantRepository,
                 value_es_repository: ValueESRepository
                 ):
        self.dw_repository = dw_mysql_repository
        self.meta_repository = meta_mysql_repository
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.full_text_repository = value_es_repository

    async def _save_tables_to_meta_db(self, tables: list[TableConfig]):
        table_infos: list[TableInfoMySQL] = []
        column_infos: list[ColumnInfoMySQL] = []

        for table in tables:
            table_info = TableInfoMySQL(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description
            )
            table_infos.append(table_info)

            column_types = await self.dw_repository.get_column_types(table.name)
            for column in table.columns:
                column_values = await self.dw_repository.get_column_values(table.name, column.name, 10)

                column_info = ColumnInfoMySQL(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_types[column.name],
                    role=column.role,
                    examples=column_values,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name
                )
                column_infos.append(column_info)

        # 2.保存元数据库信息到meta数据库
        async with self.meta_repository.session.begin():
            await self.meta_repository.save_table_infos(table_infos)
            await self.meta_repository.save_column_infos(column_infos)

        return table_infos, column_infos

    def _convert_column_info_from_mysql_to_qdrant(self, column_info: ColumnInfoMySQL) -> ColumnInfoQdrant:
        return ColumnInfoQdrant(
            id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            description=column_info.description,
            alias=column_info.alias,
            table_id=column_info.table_id
        )

    def _convert_metric_info_from_mysql_to_qdrant(self, metric_info: MetricInfoMySQL) -> MetricInfoQdrant:
        return MetricInfoQdrant(
            id=metric_info.id,
            name=metric_info.name,
            description=metric_info.description,
            relevant_columns=metric_info.relevant_columns,
            alias=metric_info.alias
        )

    async def _sync_columns_to_qdrant(self, columns: list[ColumnInfoMySQL]):
        # 创建qdrant collection
        await self.column_qdrant_repository.ensure_collection()

        records: list[dict] = []
        for column_info in columns:
            records.append(
                {'id': uuid.uuid4(),
                 'embedding_text': column_info.name,
                 'payload': self._convert_column_info_from_mysql_to_qdrant(column_info)})
            records.append(
                {'id': uuid.uuid4(), 'embedding_text': column_info.description,
                 'payload': self._convert_column_info_from_mysql_to_qdrant(column_info)})
            for alias in column_info.alias:
                records.append(
                    {'id': uuid.uuid4(), 'embedding_text': alias,
                     'payload': self._convert_column_info_from_mysql_to_qdrant(column_info)})

        ids = [uuid.uuid4() for _ in records]
        embeddings = []
        embedding_batch_size = 20
        for i in range(0, len(records), embedding_batch_size):
            batch_record = records[i:i + embedding_batch_size]
            batch_embedding_text = [record['embedding_text'] for record in batch_record]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_text)
            embeddings.extend(batch_embeddings)
        payloads = [record['payload'] for record in records]

        await self.column_qdrant_repository.upsert(ids, embeddings, payloads)

    async def _save_metrics_to_meta_db(self, metrics: list[MetricConfig]) -> list[MetricInfoMySQL]:
        metric_infos: list[MetricInfoMySQL] = []
        column_metrics: list[ColumnMetricMySQL] = []
        for metric in metrics:
            metric_info = MetricInfoMySQL(
                id=metric.name,
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias
            )
            metric_infos.append(metric_info)

            for column in metric.relevant_columns:
                column_metric = ColumnMetricMySQL(
                    column_id=column,
                    metric_id=metric.name
                )
                column_metrics.append(column_metric)
        async with self.meta_repository.session.begin():
            await self.meta_repository.save_metric_infos(metric_infos)
            await self.meta_repository.save_column_metrics(column_metrics)
        return metric_infos

    async def _sync_values_to_es(self, table_infos: list[TableInfoMySQL],
                                 column_infos: list[ColumnInfoMySQL],
                                 meta_config: MetaConfig):
        await self.full_text_repository.ensure_index()

        values: list[ValueInfoES] = []
        table_id2name = {table_info.id: table_info.name for table_info in table_infos}
        column_id2sync = {}
        for table in meta_config.tables:
            for column in table.columns:
                column_id2sync[f"{table.name}.{column.name}"] = column.sync

        for column_info in column_infos:
            table_name = table_id2name[column_info.table_id]
            column_name = column_info.name
            sync = column_id2sync[column_info.id]
            if sync:
                column_value = await self.dw_repository.get_column_values(table_name, column_name, 100000)
                values.extend([ValueInfoES(
                    id=f"{table_name}.{column_name}.{value}",
                    value=value,
                    type=column_info.type,
                    column_id=column_info.id,
                    column_name=column_info.name,
                    table_id=column_info.table_id,
                    table_name=table_name
                ) for value in column_value])
        await self.full_text_repository.batch_index(values)

    async def _sync_metrics_to_qdrant(self, metric_infos: list[MetricInfoMySQL]):
        # 创建qdrant collection
        await self.metric_qdrant_repository.ensure_collection()

        records: list[dict] = []
        for metric_info in metric_infos:
            records.append(
                {'id': uuid.uuid4(),
                 'embedding_text': metric_info.name,
                 'payload': self._convert_metric_info_from_mysql_to_qdrant(metric_info)})
            records.append(
                {'id': uuid.uuid4(),
                 'embedding_text': metric_info.description,
                 'payload': self._convert_metric_info_from_mysql_to_qdrant(metric_info)})
            for alias in metric_info.alias:
                records.append(
                    {'id': uuid.uuid4(),
                     'embedding_text': alias,
                     'payload': self._convert_metric_info_from_mysql_to_qdrant(metric_info)})
        ids = [uuid.uuid4() for _ in records]
        embeddings = []
        embedding_batch_size = 20
        for i in range(0, len(records), embedding_batch_size):
            batch_record = records[i:i + embedding_batch_size]
            batch_embedding_text = [record['embedding_text'] for record in batch_record]
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_text)
            embeddings.extend(batch_embeddings)
        payloads = [record['payload'] for record in records]

        await self.metric_qdrant_repository.upsert(ids, embeddings, payloads)

    async def build_meta_knowledge(self, config_file):
        # 1.加载配置文件
        meta_config: MetaConfig = load_config(MetaConfig, config_file)
        logger.info('加载元数据配置文件')
        if meta_config.tables:
            # 2.保存表信息到meta数据库
            table_infos, column_infos = await self._save_tables_to_meta_db(meta_config.tables)
            logger.info('保存表信息和字段信息到meta数据库')
            # 3.同步字段信息到qdrant
            await self._sync_columns_to_qdrant(column_infos)
            logger.info('同步字段信息到qdrant')
            # 4.同步字段数据到es
            await self._sync_values_to_es(table_infos, column_infos, meta_config)
            logger.info('同步字段值到es')
        if meta_config.metrics:
            # 3.保存metrics信息到meta数据库
            metric_infos = await self._save_metrics_to_meta_db(meta_config.metrics)
            logger.info('保存metric信息到meta数据库')

            # 6.同步metric信息到qdrant
            await self._sync_metrics_to_qdrant(metric_infos)
            logger.info('同步metric信息到qdrant')
        logger.info('元数据知识库构建完成')
