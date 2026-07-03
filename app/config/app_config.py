from dataclasses import dataclass
from pathlib import Path

from app.config.config_loader import load_config


@dataclass
class File:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class Console:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: File
    console: Console


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class QdrantConfig:
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    host: str
    port: int
    model: str


@dataclass
class ESConfig:
    host: str
    port: int
    index_name: str


@dataclass
class FeishuConfig:
    app_id: str
    app_secret: str


@dataclass
class LLMConfig:
    model_name: str
    sql_model_name: str
    api_key: str


@dataclass
class LangFuseConfig:
    enabled: bool
    secret_key: str
    public_key: str
    host: str


@dataclass
class RetryConfig:
    max_retries: int
    base_delay: float
    max_delay: float
    backoff_factor: float


@dataclass
class CircuitBreakerItem:
    failure_threshold: int
    recovery_timeout: int


@dataclass
class CircuitBreakerConfig:
    vector_retrieval: CircuitBreakerItem
    llm_call: CircuitBreakerItem
    sql_execution: CircuitBreakerItem


@dataclass
class LLMFallbackConfig:
    model_name: str
    backup_model_name: str


@dataclass
class SQLGuardConfig:
    block_select_star: bool
    block_no_where: bool
    max_retry_count: int


@dataclass
class RateLimitConfig:
    enabled: bool
    max_requests: int
    window_seconds: int


@dataclass
class CacheConfig:
    slow_query_threshold_ms: int
    max_cache_size: int
    cache_ttl_seconds: int


@dataclass
class QueryTimeoutConfig:
    embedding: int
    qdrant_search: int
    es_search: int
    llm_invoke: int
    sql_execute: int
    mysql_connect: int


@dataclass
class FaultToleranceConfig:
    retry: RetryConfig
    circuit_breaker: CircuitBreakerConfig
    llm_fallback: LLMFallbackConfig
    sql_guard: SQLGuardConfig
    rate_limit: RateLimitConfig
    cache: CacheConfig
    query_timeout: QueryTimeoutConfig


@dataclass
class AppConfig:
    logging: LoggingConfig
    db_meta: DBConfig
    db_dw: DBConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: ESConfig
    feishu: FeishuConfig
    llm: LLMConfig
    langfuse: LangFuseConfig
    fault_tolerance: FaultToleranceConfig


config_file = Path(__file__).parents[2] / "conf" / "app_config.yaml"
app_config: AppConfig = load_config(AppConfig, config_file)

if __name__ == "__main__":
    print(app_config.db_meta.port)
