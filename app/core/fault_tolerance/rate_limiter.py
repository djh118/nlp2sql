import time
from collections import defaultdict
from dataclasses import dataclass

from app.core.context import request_id_ctx_var
from app.core.fault_tolerance.langfuse_reporter import report_fault_event


@dataclass
class RateLimitConfig:
    enabled: bool = True
    max_requests: int = 60
    window_seconds: int = 60


class SlidingWindowRateLimiter:
    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._windows: dict[str, list[float]] = defaultdict(list)

    def _clean(self, key: str):
        now = time.time()
        cutoff = now - self.config.window_seconds
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]

    def is_allowed(self, key: str) -> bool:
        if not self.config.enabled:
            return True
        self._clean(key)
        if len(self._windows[key]) >= self.config.max_requests:
            report_fault_event(
                category="rate_limit",
                level="circuit_break",
                tag="rate_limit/blocked",
                message=f"请求限流: key={key}, 窗口内请求数={len(self._windows[key])}",
                request_id=request_id_ctx_var.get(""),
                metadata={"key": key, "count": len(self._windows[key]), "max": self.config.max_requests},
            )
            return False
        self._windows[key].append(time.time())
        return True

    def reset(self, key: str | None = None):
        if key:
            self._windows.pop(key, None)
        else:
            self._windows.clear()


_default_limiter = SlidingWindowRateLimiter()


def get_rate_limiter() -> SlidingWindowRateLimiter:
    return _default_limiter
