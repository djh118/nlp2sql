import hashlib
import json
import time
from collections import OrderedDict
from typing import Any


class LRUCache:
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _is_expired(self, timestamp: float) -> bool:
        return time.time() - timestamp > self._ttl_seconds

    def get(self, key: str) -> Any | None:
        if key not in self._cache:
            return None
        timestamp, value = self._cache[key]
        if self._is_expired(timestamp):
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return value

    def put(self, key: str, value: Any):
        if key in self._cache:
            self._cache.move_to_end(key)
        elif len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[key] = (time.time(), value)

    def clear(self):
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


def sql_cache_key(sql: str) -> str:
    normalized = " ".join(sql.strip().lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()


_sql_cache = LRUCache(max_size=100, ttl_seconds=300)
_slow_query_threshold_ms = 5000


def get_cache_manager() -> LRUCache:
    return _sql_cache


def set_slow_query_threshold(ms: int):
    global _slow_query_threshold_ms
    _slow_query_threshold_ms = ms


def get_slow_query_threshold() -> int:
    return _slow_query_threshold_ms
