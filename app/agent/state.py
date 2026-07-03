from typing import Any, TypedDict

import yaml

from app.models.es.value_info_es import ValueInfoES
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


class MetricInfoState(TypedDict):
    name: str
    description: str
    alias: list[str]


class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    description: str
    alias: list[str]
    examples: list[Any]


class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str


class DBInfoState(TypedDict):
    dialect: str
    version: str


class DataAgentState(TypedDict):
    query: str

    intent: str
    direct_response: str

    keywords: list[str]
    retrieved_metrics: list[MetricInfoQdrant]
    retrieved_columns: list[ColumnInfoQdrant]
    retrieved_values: list[ValueInfoES]

    table_infos: list[TableInfoState]
    metric_infos: list[MetricInfoState]

    date_info: DateInfoState
    db_info: DBInfoState

    sql: str
    error: str

    sql_retry_count: int
    error_category: str
    degradation_hint: str
