"""Simple LRU cache implementation."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class LRUCache(Generic[T]):
    """Least Recently Used cache with a maximum size."""

    def __init__(self, maxsize: int = 128) -> None:
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> T | None:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, value: T) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache
