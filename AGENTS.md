# Data Agent — 约束文件

## 启动命令

```bash
uv run python main.py          # 启动 FastAPI 开发服务器
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml  # 从 meta_config.yaml 初始化 Qdrant + ES
```

## 架构要点

- **FastAPI** 入口 `main.py:1` → 挂载 `chat_router` 到 `/api`，添加 `RequestIDMiddleware`，通过 `lifespan` 初始化所有客户端。
- **LangGraph** DAG 定义在 `app/agent/graph.py` — 12 个节点，`extract_keywords` 后分三路并行（`column_recall` / `value_recall` / `metric_recall`），`validate_sql` 条件边 → `correct_sql` 修正循环。
- **API**：`POST /api/query` → SSE 流式响应（`text/event-stream`）。请求体 `{"query": "..."}`。
- **流式输出**：各节点通过 `runtime.stream_writer` 推送 `{"stage": "..."}` 块，`ChatService` 层透传。

## 外部服务（配置在 `conf/app_config.yaml`）

| 服务 | 客户端管理器 | 文件位置 |
|---|---|---|
| MySQL meta | `meta_client_manager` | `app/clients/mysql_client.py` |
| MySQL dw | `dw_client_manager` | 同上 |
| Qdrant | `qdrant_client_manager` | `app/clients/qdrant_client.py` |
| Elasticsearch | `es_client_manager` | `app/clients/es_client.py` |
| Embedding (bge-large-zh-v1.5) | `embedding_client_manager` | `app/clients/embedding_client.py` |
| LLM (deepseek-chat) | langchain `init_chat_model` | `app/agent/llm.py` |

所有客户端都是**单例管理器**，在 app lifespan 阶段初始化。LangGraph 的 context（`DataAgentContext`）传递的是 repository 包装类，而非原始客户端。

## 配置加载

- `conf/app_config.yaml` — 连接信息、日志、LLM key。通过 OmegaConf dataclass merge 加载于 `app/config/app_config.py`。
- `conf/meta_config.yaml` — 表/字段/指标定义。同样方式加载于 `app/config/meta_config.py`。

## 编码约定

- **LangGraph state** = `DataAgentState`（TypedDict），**context** = `DataAgentContext`（TypedDict）。图使用 `stream_mode="custom"` + `runtime.stream_writer` 实现 SSE。
- **提示词模板** 位于 `prompts/*.prompt` 纯文本文件，通过 `app.prompt.prompt_loader.load_prompt(name)` 加载。
- **Repository 模式**：`app/repositories/` 包装数据源（mysql/qdrant/es），`app/models/` 存放对应 Pydantic/dataclass 模型。
- **全异步** — asyncmy、async ES 客户端、async Qdrant 客户端、async LangGraph 流式调用。
- **loguru 日志**，`request_id` 通过 `RequestIDMiddleware` 的 contextvar 注入。
- 没有测试、没有 lint/typecheck/CI 配置。
- `docker/` 目录为空，暂无 Docker 配置。

## Agent 流程图

```
query → extract_keywords (jieba+LLM)
         ├── column_recall (Qdrant)
         ├── value_recall (ES)
         └── metric_recall (Qdrant)
              → merge_retrieved_info
                 ├── filter_table_info
                 └── filter_metric_info
                      → add_context (日期、数据库信息)
                         → generate_sql (LLM)
                            → validate_sql
                               ├─ (错误) → correct_sql → 重新校验
                               └─ (通过) → execute_sql → 结果
```
