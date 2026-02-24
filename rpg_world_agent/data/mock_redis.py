"""Mock Redis module for local development without Redis server."""

from typing import Any, Dict, List, Optional, Union
import json
import time
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
        self._zsets: Dict[str, Dict[str, float]] = {}  # Sorted sets
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
            if key in self._zsets:
                del self._zsets[key]
        return count

    def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        count = 0
        for key in keys:
            if key in self._storage or key in self._lists or key in self._hashes or key in self._zsets:
                count += 1
        return count

    # List operations
    def rpush(self, key: str, *values: Any) -> int:
        """Push to the right (end) of a list."""
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].extend(values)
        return len(self._lists[key])

    def lpush(self, key: str, *values: Any) -> int:
        """Push to the left (start) of a list."""
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key] = list(values) + self._lists[key]
        return len(self._lists[key])

    def lrange(self, key: str, start: int, stop: int) -> List[Any]:
        """Get a range of elements from a list."""
        if key not in self._lists:
            return []
        lst = self._lists[key]
        if start < 0:
            start = len(lst) + start
        if stop < 0:
            stop = len(lst) + stop
        return lst[start:stop + 1]

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

    def llen(self, key: str) -> int:
        """Get the length of a list."""
        return len(self._lists.get(key, []))

    def lpop(self, key: str) -> Optional[Any]:
        """Pop from the left of a list."""
        if key not in self._lists or not self._lists[key]:
            return None
        return self._lists[key].pop(0)

    def rpop(self, key: str) -> Optional[Any]:
        """Pop from the right of a list."""
        if key not in self._lists or not self._lists[key]:
            return None
        return self._lists[key].pop()

    # Hash operations
    def hset(self, key: str, field: str = None, value: Any = None, mapping: Dict[str, Any] = None) -> int:
        """Set field(s) in a hash."""
        if key not in self._hashes:
            self._hashes[key] = {}
        
        count = 0
        if field is not None and value is not None:
            self._hashes[key][field] = value
            count = 1
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

    def hlen(self, key: str) -> int:
        """Get the number of fields in a hash."""
        return len(self._hashes.get(key, {}))

    def hkeys(self, key: str) -> List[str]:
        """Get all field names in a hash."""
        return list(self._hashes.get(key, {}).keys())

    def hvals(self, key: str) -> List[Any]:
        """Get all values in a hash."""
        return list(self._hashes.get(key, {}).values())

    # Sorted set operations
    def zadd(self, key: str, mapping: Dict[str, float], nx: bool = False, xx: bool = False) -> int:
        """Add members to a sorted set."""
        if key not in self._zsets:
            self._zsets[key] = {}
        
        count = 0
        for member, score in mapping.items():
            if nx and member in self._zsets[key]:
                continue
            if xx and member not in self._zsets[key]:
                continue
            if member not in self._zsets[key]:
                count += 1
            self._zsets[key][member] = score
        return count

    def zrange(self, key: str, start: int, stop: int, withscores: bool = False) -> List[Any]:
        """Get a range of members from a sorted set."""
        if key not in self._zsets:
            return []
        
        items = sorted(self._zsets[key].items(), key=lambda x: x[1])
        if start < 0:
            start = len(items) + start
        if stop < 0:
            stop = len(items) + stop
        
        result = items[start:stop + 1]
        if withscores:
            return result
        return [item[0] for item in result]

    def zrangebyscore(self, key: str, min_score: float, max_score: float, 
                      withscores: bool = False, start: int = None, num: int = None) -> List[Any]:
        """Get members with scores in range."""
        if key not in self._zsets:
            return []
        
        items = sorted(self._zsets[key].items(), key=lambda x: x[1])
        result = [(m, s) for m, s in items if min_score <= s <= max_score]
        
        if start is not None and num is not None:
            result = result[start:start + num]
        
        if withscores:
            return result
        return [item[0] for item in result]

    def zrem(self, key: str, *members: str) -> int:
        """Remove members from a sorted set."""
        if key not in self._zsets:
            return 0
        count = 0
        for member in members:
            if member in self._zsets[key]:
                del self._zsets[key][member]
                count += 1
        return count

    def zcard(self, key: str) -> int:
        """Get the number of members in a sorted set."""
        return len(self._zsets.get(key, {}))

    def zscore(self, key: str, member: str) -> Optional[float]:
        """Get the score of a member."""
        if key not in self._zsets:
            return None
        return self._zsets[key].get(member)

    def zrank(self, key: str, member: str) -> Optional[int]:
        """Get the rank of a member (0-indexed)."""
        if key not in self._zsets or member not in self._zsets[key]:
            return None
        items = sorted(self._zsets[key].items(), key=lambda x: x[1])
        for i, (m, _) in enumerate(items):
            if m == member:
                return i
        return None

    # General operations
    def expire(self, key: str, time: int) -> bool:
        """Set expiration time."""
        self._ttl[key] = time
        return True

    def ttl(self, key: str) -> int:
        """Get time to live."""
        return self._ttl.get(key, -1)

    def keys(self, pattern: str = '*') -> List[str]:
        """Get keys matching pattern."""
        import fnmatch
        all_keys = set(self._storage.keys()) | set(self._lists.keys()) | set(self._hashes.keys()) | set(self._zsets.keys())
        return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]

    def flushdb(self) -> bool:
        """Clear all data."""
        self._storage.clear()
        self._lists.clear()
        self._hashes.clear()
        self._zsets.clear()
        self._ttl.clear()
        return True

    def incr(self, key: str) -> int:
        """Increment a key's value."""
        val = int(self._storage.get(key, 0)) + 1
        self._storage[key] = str(val)
        return val

    def incrby(self, key: str, amount: int) -> int:
        """Increment a key's value by amount."""
        val = int(self._storage.get(key, 0)) + amount
        self._storage[key] = str(val)
        return val

    def decr(self, key: str) -> int:
        """Decrement a key's value."""
        return self.incrby(key, -1)

    def type(self, key: str) -> str:
        """Get the type of a key."""
        if key in self._storage:
            return "string"
        if key in self._lists:
            return "list"
        if key in self._hashes:
            return "hash"
        if key in self._zsets:
            return "zset"
        return "none"
