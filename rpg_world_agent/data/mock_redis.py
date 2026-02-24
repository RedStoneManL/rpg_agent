"""Mock Redis module for local development without Redis server."""

from typing import Any, Dict, List, Optional, Union
import json
from threading import Lock

class MockRedis:
    """Mock Redis implementation using in-memory storage."""

    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 password: Optional[str] = None, db: int = 0,
                 decode_responses: bool = True, socket_timeout: int = 2):
        self.host = host
        self.port = port
        self.db = db
        self.decode_responses = decode_responses
        self._storage: Dict[str, Any] = {}
        self._lists: Dict[str, List] = {}
        self._hashes: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, Lock] = {}
        self._ttl: Dict[str, int] = {}
        self.connected = True

    def ping(self) -> bool:
        """Check connection."""
        return self.connected

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set a key-value pair."""
        self._storage[key] = value
        if ex:
            self._ttl[key] = ex
        return True

    def setex(self, key: str, time: int, value: Any) -> bool:
        """Set a key-value pair with expiration."""
        self._storage[key] = value
        self._ttl[key] = time
        return True

    def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        return self._storage.get(key)

    def delete(self, *keys: str) -> int:
        """Delete keys."""
        count = 0
        for key in keys:
            if key in self._storage:
                del self._storage[key]
                count += 1
            if key in self._lists:
                del self._lists[key]
            if key in self._hashes:
                del self._hashes[key]
        return count

    def rpush(self, key: str, *values: Any) -> int:
        """Push to the right (end) of a list."""
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].extend(values)
        return len(self._lists[key])

    def lrange(self, key: str, start: int, stop: int) -> List[Any]:
        """Get a range of elements from a list."""
        if key not in self._lists:
            return []
        lst = self._lists[key]
        # Handle negative indices
        if start < 0:
            start = len(lst) + start
        if stop < 0:
            stop = len(lst) + stop
        return lst[start:stop + 1]

    def hset(self, key: str, field: str = None, value: Any = None, mapping: Dict[str, Any] = None) -> int:
        """Set field(s) in a hash. Supports both (key, field, value) and (key, mapping=...) patterns."""
        if key not in self._hashes:
            self._hashes[key] = {}
        
        count = 0
        # Handle individual field/value
        if field is not None and value is not None:
            self._hashes[key][field] = value
            count = 1
        # Handle mapping dict
        if mapping:
            self._hashes[key].update(mapping)
            count = len(mapping)
        return count

    def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all fields and values in a hash."""
        return self._hashes.get(key, {})

    def hget(self, key: str, field: str) -> Optional[Any]:
        """Get a single field from a hash."""
        if key not in self._hashes:
            return None
        return self._hashes[key].get(field)

    def hexists(self, key: str, field: str) -> bool:
        """Check if a field exists in a hash."""
        if key not in self._hashes:
            return False
        return field in self._hashes[key]

    def hdel(self, key: str, *fields: str) -> int:
        """Delete fields from a hash."""
        if key not in self._hashes:
            return 0
        count = 0
        for field in fields:
            if field in self._hashes[key]:
                del self._hashes[key][field]
                count += 1
        return count

    def lindex(self, key: str, index: int) -> Optional[Any]:
        """Get an element by index from a list."""
        if key not in self._lists:
            return None
        lst = self._lists[key]
        if index < 0:
            index = len(lst) + index
        if 0 <= index < len(lst):
            return lst[index]
        return None

    def expire(self, key: str, time: int) -> bool:
        """Set expiration time (mock - does nothing)."""
        self._ttl[key] = time
        return True

    def keys(self, pattern: str = '*') -> List[str]:
        """Get keys matching pattern."""
        import fnmatch
        all_keys = list(set(self._storage.keys()) | set(self._lists.keys()) | set(self._hashes.keys()))
        return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]

    def flushdb(self) -> bool:
        """Clear all data."""
        self._storage.clear()
        self._lists.clear()
        self._hashes.clear()
        self._ttl.clear()
        return True
