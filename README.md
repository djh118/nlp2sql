# Data Agent

基于 LangGraph 的数据查询 Agent，通过自然语言查询自动生成并执行 SQL。

## 项目概述

Data Agent 是一个智能数据查询系统，用户可以用自然语言提问，系统自动：
1. 提取查询关键词
2. 从向量数据库召回相关的字段、指标、字段值信息
3. 合并并筛选召回信息
4. 生成 SQL 语句
5. 校验 SQL 正确性
6. 执行 SQL 返回结果

## 技术栈

- **框架**: FastAPI + LangGraph
- **LLM**: DeepSeek
- **向量数据库**: Qdrant (字段/指标向量存储)
- **搜索引擎**: Elasticsearch (字段值搜索)
- **关系数据库**: MySQL (Meta 库 + DW 库)
- **Embedding**: BAAI/bge-large-zh-v1.5

## 项目结构

```
data-agent/
├── app/
│   ├── agent/               # Agent 核心
│   │   ├── graph.py        # LangGraph 流程定义
│   │   ├── state.py       # 状态定义
│   │   ├── context.py     # 上下文
│   │   ├── llm.py        # LLM 配置
│   │   └── nodes/         # 各处理节点
│   │       ├── extract_keywords.py     # 关键词提取
│   │       ├── column_recall.py       # 字段召回
│   │       ├── value_recall.py       # 字段值召回
│   │       ├── metric_recall.py      # 指标召回
│   │       ├── merge_retrieved_info.py # 信息合并
│   │       ├── filter_table_info.py  # 表信息筛选
│   │       ├── filter_metric_info.py # 指标筛选
│   │       ├── add_context.py       # 添加上下文
│   │       ├── generate_sql.py     # SQL生成
│   │       ├── validate_sql.py  # SQL校验
│   │       ├── correct_sql.py   # SQL修正
│   │       └── execute_sql.py  # SQL执行
│   ├── api/                 # API层
│   │   ├── deps.py         # 依赖注入
│   │   └── routers/        # 路由
│   ├── clients/            # 客户端
│   │   ├── mysql_client.py
│   │   ├── qdrant_client.py
│   │   ├── es_client.py
│   │   └── embedding_client.py
│   ├── repositories/       # 数据访问层
│   ├── models/             # 数据模型
│   ├── core/               # 核心组件
│   ├── service/            # 服务层
│   └── config/             # 配置
├── conf/                   # 配置文件
│   ├── app_config.yaml
│   └── meta_config.yaml
├── prompts/                # 提示词模板
└── main.py                # 入口
```

## Agent 工作流程

```
query → extract_keywords → [column_recall, value_recall, metric_recall]
                              ↓
                        merge_retrieved_info
                              ↓
              [filter_table_info, filter_metric_info]
                              ↓
                           add_context
                              ↓
                          generate_sql
                              ↓
                          validate_sql
                              ↓
                         execute_sql → result
```

### 节点说明

| 节点 | 说明 |
|------|------|
| extract_keywords | 使用 jieba 从查询中提取关键词 |
| column_recall | 从 Qdrant 召回相关字段信息 |
| value_recall | 从 Elasticsearch 召回字段值 |
| metric_recall | 从 Qdrant 召回指标信息 |
| merge_retrieved_info | 合并召回信息 |
| filter_table_info | 筛选表信息 |
| filter_metric_info | 筛选指标信息 |
| add_context | 添加上下文（日期、数据库信息） |
| generate_sql | 调用 LLM 生成 SQL |
| validate_sql | 校验 SQL 语��� |
| correct_sql | 修正 SQL 错误 |
| execute_sql | 执行 SQL |

## API

### 查询接口

```
POST /api/query
```

请求：
```json
{
  "query": "统计2025年1月各品类销售额"
}
```

响应：SSE 流式返回各阶段结果

## 配置

配置文件：`conf/app_config.yaml`

| 配置项 | 说明 |
|--------|------|
| db_meta | Meta 数据库连接 |
| db_dw | DW 数据库连接 |
| qdrant | Qdrant 向量数据库 |
| embedding | Embedding 服务 |
| es | Elasticsearch |
| llm | LLM 配置 |

## 启动

```bash
uv run python main.py
```