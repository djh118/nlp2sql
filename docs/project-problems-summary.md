# Data Agent — 项目问题总结（面试用）

## 项目简介

基于 LangGraph + FastAPI 的自然语言转 SQL 查询系统。用户输入中文查询 → LLM 理解意图 → 向量/ES 召回表结构 → LLM 生成 SQL → 校验 → 执行 → 返回结果。集成了全链路容错（断路器、重试、降级、SQL 守卫）、Langfuse 可观测性。

---

## 一、LLM 模型选型与 Prompt 工程

### 1.1 模型质量：deepseek-chat 对复杂 Prompt 指令跟随差

**现象**：`deepseek-chat` 生成 SQL 时频繁出现 `/* select#1 */` 前缀、`WHERE true` 恒真条件、JOIN 无 ON、字段前加 schema 前缀 (`dw.dp.product_id`) 等问题。

**根因**：`deepseek-chat` 是通用对话模型，对多约束结构化输出（10+ 条规则）的指令跟随能力弱。深层原因是 chat 模型缺少推理步骤，容易在长上下文中"遗忘"尾部约束。

**解决**：
- 主模型切为 `deepseek-reasoner`（内部走 Chain-of-Thought），仅 SQL 生成节点使用，非 SQL 节点（关键词提取、意图分类、召回）仍用 `deepseek-chat` 保速度
- 两层兜底：`sanitize_sql()` 正则剥离注释 + `guard_sql()` 规则拦截

**面试价值**：不同 LLM 的指令跟随能力差异、CoT 推理 vs 直接输出的取舍、模型路由策略（不同节点用不同模型）

### 1.2 LangChain PromptTemplate input_variables 未包含模板变量

**现象**：虽然提示词文件中使用了 `{query}`，但 `PromptTemplate(input_variables=[...])` 中未列出 `query`。

**根因**：LangChain 的 `input_variables` 声明与实际模板变量不一致，依赖 LangChain 的容错机制（自动推断/宽松模式）运行。

**解决**：统一使用 `template_format="f-string"` 并确保 `input_variables` 与模板变量完整匹配。

**面试价值**：LangChain PromptTemplate 的变量绑定机制、框架隐式行为与显式声明的差异

---

## 二、SQL 安全守卫（Guard）设计

### 2.1 全表扫描检测误伤合法 JOIN ... ON 查询

**现象**：`FROM fact_order JOIN dim_product ON ...` 被 `_has_no_where` 拦截，报"缺少 WHERE 条件"。

**根因**：守卫逻辑仅判断"有 FROM 无 WHERE"，未考虑 JOIN 自带的 ON 条件本身就是关联过滤，无需额外 WHERE。

**解决**：`_has_no_where` 改为统计 FROM 子句中 JOIN 和 ON 的数量，仅当 JOIN 数 == ON 数时放行（每个 JOIN 都有 ON 就不需要 WHERE）。

### 2.2 笛卡尔积检测误判 WHERE 关联条件

**现象**：`FROM a JOIN b WHERE a.id = b.id`（关联条件在 WHERE 里）被 `_is_cartesian_product` 拦截。

**根因**：检测逻辑仅算 FROM 部分中的 `join` 和 `on` 关键字，未考虑 WHERE 子句中的跨表关联。

**解决**：存在 WHERE 子句时直接跳过笛卡尔积检测（`_has_no_where` 负责拦截完全无过滤的全表扫描）。

### 2.3 Empty SQL 进入 EXPLAIN 校验引发连锁崩溃

**现象**：SQL 被 guard 拦截后返回 `sql=""` → `validate_sql` 执行 `EXPLAIN ""` → MySQL 报 1064 语法错 → 原始 guard 错误被覆盖 → `correct_sql` 收到空 SQL + 无意义错误 → LLM 浪费一次调用。

**根因**：`validate_sql` 无空 SQL 保护；`_decide_sql_next` 没区分"守卫拦截的不可修复错误"和"可修正的 SQL 语法错误"。

**解决**：
- `validate_sql`：空 SQL 时跳过 EXPLAIN，保留原始错误
- `_decide_sql_next`：SQL 为空或 `error_category=sql_guard` 时直接 END，不走 correct_sql 循环
- `generate_sql`：guard 拦截时设置 `error_category: "sql_guard"`

### 2.4 LLM 输出夹杂 EXPLAIN 注释标记

**现象**：LLM 在 SQL 前输出 `/* select#1 */`（MySQL EXPLAIN 格式的输出前缀），导致 SQL 无法直接执行。

**根因**：模型训练数据含 EXPLAIN 输出，模型将注释视为 SQL 的一部分输出。

**解决**：三段式清理——`llm.py` 输出后 `sanitize_sql()` → `guard_sql` 入口再清一次 → `validate_sql` 最后兜底清理。

**面试价值**：安全守卫链的设计哲学（Defense in Depth）、错误传播与拦截策略、不可修复错误 vs 可修复错误的分类路由

---

## 三、LangGraph 流程设计

### 3.1 SQL 修正循环缺少回环边

**现象**：`correct_sql` 节点输出新 SQL 后流程结束，不会重新进入 `validate_sql`。

**根因**：`graph_builder.add_edge("correct_sql", "validate_sql")` 未添加。

**解决**：补充该边，使流程成为 `validate_sql → correct_sql → validate_sql` 循环，配合 `sql_retry_count` 限次退出。

### 3.2 修正循环无限重试

**现象**：SQL 反复修正仍错时，流程无限循环。

**根因**：无重试计数和上限拦截。

**解决**：`DataAgentState` 增加 `sql_retry_count` 字段，`_decide_sql_next` 中超过 `max_retry_count` 时终止。

**面试价值**：LangGraph 有向图的工作流控制、循环边与终止条件设计、状态驱动的条件路由

---

## 四、Python 3.12 asyncio + PyCharm 兼容性

### 4.1 `_patch_task` 拒绝 `eager_start` 参数

**现象**：PyCharm 2024.2 调试器 patch 了 `asyncio.Task.__init__()`，但 Python 3.12 新增了 `eager_start` 关键字参数，导致 `TypeError: __init__() got an unexpected keyword argument 'eager_start'`。

**根因**：PyCharm 的 `_patch_task` 未适配 Python 3.12 的 Task API 变更。

**触发场景**：
- `asyncio.wait_for()` — 内部创建 Task，触发 `_patch_task`
- 使用 PyCharm debugger 断点调试时

**解决**：
- 用 `asyncio.timeout()` 上下文管理器替代 `asyncio.wait_for()`（不创建 Task）
- 生产环境无问题（`python main.py` 正常）
- 本地调试用 `run_debug.py` + `if __name__ == "__main__"` + 终端执行

### 4.2 `_patch_asyncio` 拒绝 `loop_factory` 参数

**现象**：uvicorn >= 0.30 传递 `loop_factory` 给 `asyncio.run()`，PyCharm patch 拒绝了该参数。

**解决**：锁定 `uvicorn<0.30`（`0.29.0`）。

**面试价值**：Python 3.12 asyncio 变更对三方框架的影响、IDE debugger patch 的限制与规避、生产与开发环境的差异

---

## 五、Langfuse 可观测性集成

### 5.1 故障事件观测类型选择

**问题**：容错事件（断路器打开、SQL 拦截、限流拒绝）应使用 Langfuse 的 `event` 类型而非 `span` 类型。

**理由**：`event` 表示离散的点状事件，`span` 表示有持续时间的操作。断路器跳闸、SQL 拦截都是一瞬间的判定，不涉及持续时长。

### 5.2 `create_score` 要求 `trace_id`

**问题**：Langfuse 的 `create_score` 评分 API 必须传入 `trace_id` 才能关联到已有 trace。

**解决**：通过 `client.get_current_trace_id()` 获取当前 trace 的 ID，或用 `trace_context` 参数传递。无请求上下文的事件（如 lifespan 阶段）创建独立 trace。

### 5.3 `Auth check` 启动时警告

**问题**：启动时 Langfuse 打印 `Auth check` 警告，因为 `.env` 在 `load_dotenv()` 运行时才加载，而 `Langfuse()` 构造函数在模块级别先执行。

**解决**：确保 `load_dotenv()` 在第一次 `Langfuse()` 调用之前执行。仅影响日志输出，不影响功能。

**面试价值**：可观测性 SDK 的使用最佳实践、事件 vs Span 的语义区别、trace 关联策略

---

## 六、客户端与基础设施问题

### 6.1 HuggingFaceEndpointEmbeddings 拒绝 `timeout` 字段

**现象**：Pydantic 模型 `HuggingFaceEndpointEmbeddings` 声明了 `timeout` 字段，但 Pydantic v2 的 `extra="forbid"` 拒绝额外字段。

**根因**：LangChain 的 `HuggingFaceEndpointEmbeddings` 使用 Pydantic v1 风格，模型初始化时不接受未声明的构造参数。`timeout` 不在其模型字段中。

**解决**：回退为 bare init（不传 `timeout`），通过外层 CircuitBreaker 超时保护。

**面试价值**：LangChain 各组件的 Pydantic 版本兼容性、被动超时 vs 主动超时的设计取舍

### 6.2 MySQL KILL CONNECTION 与慢查询缓存

**问题**：慢 SQL 可能挂起数据库连接，需要超时后主动 KILL。

**解决**：`dw_mysql_repository` 中记录 `connection_id` → 超时后 `KILL CONNECTION <id>` → 结果写入 LRU 缓存。

---

## 七、架构设计决策

| 决策 | 方案 | 理由 |
|------|------|------|
| 容错层次 | Retry → CircuitBreaker → Fallback → Report | 各层职责单一，可独立配置 |
| SQL 守卫位置 | `generate_sql` 输出后 + `validate_sql` 入口 | 双重校验，防绕过 |
| 错误传播 | 不可修复错误（guard 拦截）直接 END | 避免浪费 LLM 调用 |
| 模型路由 | 非 SQL = chat（快），SQL = reasoner（准） | 速度与质量兼顾 |
| asyncio 超时 | `asyncio.timeout()` 而非 `wait_for()` | 规避 PyCharm debugger bug |

---

## 八、关键数据

- **Python**: 3.12
- **框架**: FastAPI + LangGraph + LangChain
- **LLM**: deepseek-chat（非 SQL）/ deepseek-reasoner（SQL 生成）
- **向量库**: Qdrant
- **搜索引擎**: Elasticsearch
- **数据库**: MySQL 8.0.31 (asyncmy)
- **嵌入**: bge-large-zh-v1.5
- **可观测**: Langfuse
- **全量文件**: ~24 文件改动，+867 / −238 行（容错系统主体）
