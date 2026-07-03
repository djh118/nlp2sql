import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from app.core.context import request_id_ctx_var
from app.core.fault_tolerance.langfuse_reporter import report_fault_event
from app.core.logging import logger


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_requests: int = 3


class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_requests = 0

    @property
    def state(self) -> CircuitState:
        return self._state

    def _on_success(self):
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"[circuit_breaker] {self.name} 半开试探成功，恢复为 CLOSED")
            report_fault_event(
                category="circuit_breaker",
                level="recover",
                tag=f"circuit_breaker/{self.name}/recover",
                message=f"熔断器 {self.name} 半开试探成功，已恢复",
                request_id=request_id_ctx_var.get(""),
            )
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_requests = 0

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"[circuit_breaker] {self.name} 半开试探失败，回到 OPEN")
            self._state = CircuitState.OPEN
            self._half_open_requests = 0
            report_fault_event(
                category="circuit_breaker",
                level="circuit_break",
                tag=f"circuit_breaker/{self.name}/half_open_fail",
                message=f"熔断器 {self.name} 半开试探失败，回到 OPEN",
                request_id=request_id_ctx_var.get(""),
                metadata={"failure_count": self._failure_count},
            )
        elif self._failure_count >= self.config.failure_threshold:
            logger.warning(
                f"[circuit_breaker] {self.name} 连续 {self._failure_count} 次失败，熔断 OPEN"
            )
            self._state = CircuitState.OPEN
            report_fault_event(
                category="circuit_breaker",
                level="circuit_break",
                tag=f"circuit_breaker/{self.name}/open",
                message=f"熔断器 {self.name} 连续 {self._failure_count} 次失败，熔断 OPEN",
                request_id=request_id_ctx_var.get(""),
                metadata={"failure_count": self._failure_count},
            )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.config.recovery_timeout:
                logger.info(f"[circuit_breaker] {self.name} 恢复超时到期，进入 HALF_OPEN")
                self._state = CircuitState.HALF_OPEN
                self._half_open_requests = 0
            else:
                raise CircuitBreakerOpenError(
                    f"[circuit_breaker] {self.name} 熔断中，请求被拒绝"
                )

        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_requests >= self.config.half_open_max_requests:
                raise CircuitBreakerOpenError(
                    f"[circuit_breaker] {self.name} 半开试探已满，请求被拒绝"
                )
            self._half_open_requests += 1

        try:
            import inspect
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise


class CircuitBreakerOpenError(Exception):
    pass


_circuit_breaker_registry: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
    if name not in _circuit_breaker_registry:
        _circuit_breaker_registry[name] = CircuitBreaker(name, config)
    return _circuit_breaker_registry[name]


def reset_all():
    _circuit_breaker_registry.clear()
