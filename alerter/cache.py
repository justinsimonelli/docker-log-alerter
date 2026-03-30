import hashlib
from cachetools import TTLCache


class DeduplicationCache:
    """TTL-based cache to prevent duplicate alerts."""

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def _hash(self, container: str, message: str) -> str:
        """Create a hash key from container + message."""
        content = f"{container}:{message}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def is_seen(self, container: str, message: str) -> bool:
        """Check if this error has been seen recently."""
        key = self._hash(container, message)
        return key in self._cache

    def mark_seen(self, container: str, message: str) -> None:
        """Mark an error as seen."""
        key = self._hash(container, message)
        self._cache[key] = True

    def check_and_mark(self, container: str, message: str) -> bool:
        """
        Check if seen, and if not, mark it.
        Returns True if this is a NEW error (should alert).
        Returns False if this is a DUPLICATE (skip alert).
        """
        if self.is_seen(container, message):
            return False
        self.mark_seen(container, message)
        return True
