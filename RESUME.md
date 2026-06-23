# Data Agent - 智能数据查询系统

## 项目介绍

基于 LangGraph + DeepSeek 的智能数据查询 Agent，能够理解用户的自然语言问题，自动生成并执行 SQL 查询并返回结果。

## 工作职责

1. **需求分析**：理解用户自然语言查询意图，提取关键信息
2. **语义召回**：通过 Qdrant 向量数据库召回相关字段、指标信息；通过 Elasticsearch 搜索字段值
3. **SQL 生成**：利用 DeepSeek LLM 根据召回的元数据和上下文自动生成 SQL 语句
4. **SQL 校验与修正**：验证 SQL 语法正确性，错误时自动修正
5. **结果返回**：执行 SQL 并流式返回查询结果

## 技术栈

| 类别 | 技术 |
|------|------|
| 后端框架 | FastAPI、LangGraph |
| 大语言模型 | DeepSeek Chat |
| 向量数据库 | Qdrant |
| 搜索引擎 | Elasticsearch |
| 关系数据库 | MySQL (Meta / DW) |
| Embedding | BAAI/bge-large-zh-v1.5 |
| 分词 | jieba |

## 核心技能

- **LangGraph 工作流设计**：实现了 13 个处理节点的 DAG 流程
- **多数据源整合**：MySQL + Qdrant + ES 联合查询
- **流式响应**：SSE 实现实时返回各阶段处理结果
- **SQL 校验与修正**：自动验证并修正生成的 SQL

## 项目结构

```
data-agent/
├── app/
│   ├── agent/           # Agent 核心
│   │   ├── graph.py    # LangGraph 流程定义
│   │   ├── state.py   # 状态定义
│   │   └── nodes/     # 13个处理节点
│   ├── api/           # FastAPI 路由
│   ├── clients/       # MySQL/Qdrant/ES 客户端
│   ├── repositories/  # 数据访问层
│   └── models/        # 数据模型
├── prompts/           # 提示词模板
└── conf/             # 配置文件
```

## Agent 处理流程

```
用户 query
    ↓
extract_keywords (jieba分词)
    ↓
[column_recall, value_recall, metric_recall] (向量召回)
    ↓
merge_retrieved_info (信息合并)
    ↓
[filter_table_info, filter_metric_info] (筛选)
    ↓
add_context (添加上下文)
    ↓
generate_sql (LLM生成)
    ↓
validate_sql (语法校验)
    ↓
execute_sql (执行返回)
```

## 关键代码

- LangGraph 流程定义：`app/agent/graph.py`
- LLM SQL 生成：`app/agent/nodes/generate_sql.py`
- 向量召回：`app/agent/nodes/column_recall.py`、`metric_recall.py`

## 启动方式

```bash
uv run python main.py
```

API 端点：`POST /api/query`