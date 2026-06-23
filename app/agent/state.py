from typing import Any, TypedDict

import yaml

from app.models.es.value_info_es import ValueInfoES
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


class MetricInfoState(TypedDict):
    name: str  # 指标名称
    description: str  # 指标描述
    alias: list[str]  # 指标别名


class ColumnInfoState(TypedDict):
    name: str  # 字段名称
    type: str  # 字段类型
    role: str  # 字段角色（primary_key/foreign_key/dimension/measure）
    description: str  # 字段描述
    alias: list[str]  # 字段别名
    examples: list[Any]  # 字段示例


class TableInfoState(TypedDict):
    name: str  # 表名称
    role: str  # 表角色（fact/dim）
    description: str  # 表描述
    columns: list[ColumnInfoState]  # 字段信息


class DateInfoState(TypedDict):
    date: str  # 日期
    weekday: str  # 星期
    quarter: str  # 季度


class DBInfoState(TypedDict):
    dialect: str  # 数据库方言
    version: str  # 数据库版本


class DataAgentState(TypedDict):
    query: str  # 查询

    keywords: list[str]  # 关键词列表，由query分词和LLM生成得到，用于召回信息
    retrieved_metrics: list[MetricInfoQdrant]  # 召回的指标信息
    retrieved_columns: list[ColumnInfoQdrant]  # 召回的字段信息
    retrieved_values: list[ValueInfoES]  # 召回的字段值信息

    table_infos: list[TableInfoState]  # 合并的表信息
    metric_infos: list[MetricInfoState]  # 召回的指标信息

    date_info: DateInfoState  # 当前的日期信息
    db_info: DBInfoState  # 数据库信息

    sql: str  # 生成的SQL语句
    error: str  # 校验SQL语句的错误信息


if __name__ == '__main__':
    columns = [
        ColumnInfoState(
            name="id",
            type="int",
            role="primary_key",
            description="编号",
            alias=["编号"],
            examples=["1", "2", "3"]
        ),
        ColumnInfoState(
            name="name",
            type="varchar",
            role="dimension",
            description="名称",
            alias=["名称"],
            examples=["张三", "李四", "王五"]
        ),
        ColumnInfoState(
            name="age",
            type="int",
            role="measure",
            description="年龄",
            alias=["年龄"],
            examples=["18", "19", "20"]
        )
    ]
    table = TableInfoState(
        name="user",
        role="fact",
        description="用户信息",
        columns=columns
    )

    print(yaml.safe_dump(table, allow_unicode=True, sort_keys=False))
