from enum import Enum
from typing import Tuple


class ErrorCategory(str, Enum):
    VECTOR_RETRIEVAL = "vector_retrieval"
    LLM_CALL = "llm_call"
    SQL_GENERATION = "sql_generation"
    SQL_EXECUTION = "sql_execution"
    RATE_LIMIT = "rate_limit"
    AUTH_PERMISSION = "auth_permission"
    INTERNAL = "internal"


class FaultToleranceLevel(str, Enum):
    RETRY = "retry"
    DEGRADE = "degrade"
    CIRCUIT_BREAK = "circuit_break"
    BLOCK = "block"
    FATAL = "fatal"


_ERROR_MAP: list[tuple[str, ErrorCategory, FaultToleranceLevel]] = [
    ("connection refused", ErrorCategory.VECTOR_RETRIEVAL, FaultToleranceLevel.RETRY),
    ("timeout", ErrorCategory.LLM_CALL, FaultToleranceLevel.RETRY),
    ("rate limit", ErrorCategory.RATE_LIMIT, FaultToleranceLevel.RETRY),
    ("token limit", ErrorCategory.LLM_CALL, FaultToleranceLevel.DEGRADE),
    ("insufficient quota", ErrorCategory.RATE_LIMIT, FaultToleranceLevel.CIRCUIT_BREAK),
    ("permission denied", ErrorCategory.AUTH_PERMISSION, FaultToleranceLevel.BLOCK),
    ("access denied", ErrorCategory.AUTH_PERMISSION, FaultToleranceLevel.BLOCK),
    ("connection pool exhausted", ErrorCategory.SQL_EXECUTION, FaultToleranceLevel.RETRY),
    ("deadlock", ErrorCategory.SQL_EXECUTION, FaultToleranceLevel.RETRY),
    ("lock wait timeout", ErrorCategory.SQL_EXECUTION, FaultToleranceLevel.RETRY),
    ("collection .* not found", ErrorCategory.VECTOR_RETRIEVAL, FaultToleranceLevel.DEGRADE),
    ("index .* not found", ErrorCategory.VECTOR_RETRIEVAL, FaultToleranceLevel.DEGRADE),
    ("no such index", ErrorCategory.VECTOR_RETRIEVAL, FaultToleranceLevel.DEGRADE),
]


def classify_error(e: Exception) -> Tuple[ErrorCategory, FaultToleranceLevel, str]:
    msg = str(e).lower()
    for pattern, category, level in _ERROR_MAP:
        import re
        if re.search(pattern, msg):
            return category, level, f"{category.value}/{level.value}"
    if isinstance(e, ConnectionError):
        return ErrorCategory.VECTOR_RETRIEVAL, FaultToleranceLevel.RETRY, "vector_retrieval/retry"
    if isinstance(e, TimeoutError):
        return ErrorCategory.LLM_CALL, FaultToleranceLevel.RETRY, "llm_call/retry"
    return ErrorCategory.INTERNAL, FaultToleranceLevel.FATAL, "internal/fatal"


def build_langfuse_tags(category: ErrorCategory, level: FaultToleranceLevel) -> dict:
    return {
        "error_category": category.value,
        "fault_tolerance_level": level.value,
        "error_tag": f"{category.value}/{level.value}",
    }
