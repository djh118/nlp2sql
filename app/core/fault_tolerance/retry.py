import asyncio
from dataclasses import dataclass
from functools import wraps
from typing import Callable

from app.core.fault_tolerance.error_types import classify_error, FaultToleranceLevel
from app.core.logging import logger


@dataclass
class RetryConfig:
    max_retries: int = 2
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    retryable_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
        OSError,
    )
    is_read_only: bool = True


class NonRetryableError(Exception):
    pass


def is_retryable(e: Exception, config: RetryConfig) -> bool:
    if isinstance(e, NonRetryableError):
        return False
    for exc_type in config.retryable_exceptions:
        if isinstance(e, exc_type):
            return True
    category, level, _ = classify_error(e)
    if level in (FaultToleranceLevel.BLOCK, FaultToleranceLevel.FATAL):
        return False
    return True


def async_retry(config: RetryConfig | None = None):
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if not is_retryable(e, config):
                        raise
                    if attempt < config.max_retries:
                        delay = min(
                            config.base_delay * (config.backoff_factor ** attempt),
                            config.max_delay,
                        )
                        logger.warning(
                            f"[retry] {func.__name__} 失败 (attempt {attempt + 1}/{config.max_retries + 1}): "
                            f"{e}, {delay}s 后重试"
                        )
                        await asyncio.sleep(delay)
            raise last_exception

        return wrapper

    return decorator
