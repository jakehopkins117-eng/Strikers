"""
Simple in-memory cache for Strikers.

The cache prevents the application from making the same MLB API
request multiple times during one session.
"""

from copy import deepcopy
from time import monotonic
from typing import Any


class MemoryCache:
    """
    Store temporary values in memory with expiration times.

    Cached information is automatically cleared when Strikers closes.
    """

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 300,
    ) -> None:
        """
        Store a value in the cache.

        Args:
            key: Unique identifier for the cached value.
            value: Data that should be stored.
            ttl_seconds: Number of seconds before the value expires.
        """

        expiration_time = monotonic() + ttl_seconds

        self._items[key] = {
            "value": deepcopy(value),
            "expires_at": expiration_time,
        }

    def get(self, key: str) -> Any | None:
        """
        Retrieve a value from the cache.

        Returns None when the key does not exist or has expired.
        """

        item = self._items.get(key)

        if item is None:
            return None

        if monotonic() >= item["expires_at"]:
            self.delete(key)
            return None

        return deepcopy(item["value"])

    def delete(self, key: str) -> None:
        """Remove one cached value."""

        self._items.pop(key, None)

    def clear(self) -> None:
        """Remove every cached value."""

        self._items.clear()

    def remove_expired(self) -> None:
        """Remove all expired values from the cache."""

        current_time = monotonic()

        expired_keys = [
            key
            for key, item in self._items.items()
            if current_time >= item["expires_at"]
        ]

        for key in expired_keys:
            self.delete(key)

    def size(self) -> int:
        """Return the number of active cached values."""

        self.remove_expired()
        return len(self._items)


mlb_cache = MemoryCache()