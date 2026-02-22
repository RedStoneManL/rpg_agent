"""Mock Redis client for testing."""

import json
from typing import Any, Dict, List, Optional, Set
from unittest.mock import MagicMock


class MockRedis:
    """
    In-memory mock Redis client for testing.
    Simulates Redis operations without requiring actual Redis instance.
    """

    def __init__(self):
        # Storage: Dict[str, Any]
        self._storage: Dict[str, Any] = {}

        # Hash storage: Dict[str, Dict[str, Any]]
        self._hashes: Dict[str, Dict[str, Any]] = {}

        # List storage: Dict[str, List[Any]]
        self._lists: Dict[str, List[Any]] = {}

        # Set storage: Dict[str, Set[Any]]
        self._sets: Dict[str, Set[Any]] = {}

        # Sorted set storage: Dict[str, Dict[float, Set[Any]]]
        self._sorted_sets: Dict[str, Dict[float, Set[Any]]] = {}

        # Available IDs
        self._available_ids: List[int] = list(range(1, 256))

        # Mock methods
        self.ping = MagicMock(return_value=True)
        self.exists = self._exists
        self.get = self._get
        self.set = self._set
        self.setex = self._setex
        self.delete = self._delete
        self.hget = self._hget
        # hset wrapper is defined later to handle mapping parameter
        self.hgetall = self._hgetall
        self.hexists = self._hexists
        self.rpush = self._rpush
        self.lrange = self._lrange
        self.rpop = self._rpop
        self.sadd = self._sadd
        self.smembers = self._smembers
        self.srem = self._srem
        self.scard = self._scard
        self.sismember = self._sismember
        self.zadd = self._zadd
        self.zrange = self._zrange
        self.zrevrange = self._zrevrange
        self.zrangebyscore = self._zrangebyscore
        self.zrevrangebyscore = self._zrevrangebyscore
        self.zscore = self._zscore
        self.incr = self._incr
        self.expire = self._expire
        self.ttl = self._ttl
        self.keys = self._keys
        self.flushdb = self._flushdb
        self.incrby = self._incrby
        self.decr = self._decr

    def _exists(self, *keys: str) -> int:
        """Check if keys exist."""
        count = 0
        for key in keys:
            if key in self._storage or key in self._hashes or key in self._lists:
                count += 1
        return count

    def _get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return self._storage.get(key)

    def _set(self, key: str, value: Any) -> bool:
        """Set key-value pair."""
        # Clear any existing data in other structures
        if key in self._hashes:
            del self._hashes[key]
        if key in self._lists:
            del self._lists[key]
        if key in self._sets:
            del self._sets[key]
        if key in self._sorted_sets:
            del self._sorted_sets[key]

        self._storage[key] = value
        return True

    def _setex(self, key: str, seconds: int, value: Any) -> bool:
        """Set key with expiration time."""
        # For simplicity, we ignore expiration in the mock
        # In a real implementation, we'd need to track TTL
        self._set(key, value)
        return True

    def _delete(self, *keys: str) -> int:
        """Delete keys."""
        count = 0
        for key in keys:
            if self._exists(key):
                count += 1
                self._storage.pop(key, None)
                self._hashes.pop(key, None)
                self._lists.pop(key, None)
                self._sets.pop(key, None)
                self._sorted_sets.pop(key, None)
        return count

    def _hset(self, name: str, key: str, value: Any) -> int:
        """Set hash field."""
        if name not in self._hashes:
            self._hashes[name] = {}
        self._hashes[name][key] = value
        return 1

    def _hset_multi(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set multiple hash fields."""
        if name not in self._hashes:
            self._hashes[name] = {}
        self._hashes[name].update(mapping)
        return len(mapping)

    def _hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field value."""
        return self._hashes.get(name, {}).get(key)

    def _hgetall(self, name: str) -> Dict[str, Any]:
        """Get all hash fields."""
        return self._hashes.get(name, {}).copy()

    def _hexists(self, name: str, key: str) -> bool:
        """Check if hash field exists."""
        return key in self._hashes.get(name, {})

    def _rpush(self, name: str, *values: Any) -> int:
        """Push to right side of list."""
        if name not in self._lists:
            self._lists[name] = []
        self._lists[name].extend(values)
        return len(self._lists[name])

    def _lrange(self, name: str, start: int, end: int) -> List[Any]:
        """Get range of list elements."""
        lst = self._lists.get(name, [])
        # Convert negative indices
        length = len(lst)
        if start < 0:
            start = max(length + start, 0)
        if end < 0:
            end = length + end
        # Cap end at length
        end = min(end, length - 1)
        if start > end:
            return []
        return lst[start:end+1]

    def _rpop(self, name: str) -> Optional[Any]:
        """Pop from right side of list."""
        if name in self._lists:
            return self._lists[name].pop()
        return None

    def _sadd(self, name: str, *members: Any) -> int:
        """Add members to set."""
        if name not in self._sets:
            self._sets[name] = set()
        count = 0
        for member in members:
            if member not in self._sets[name]:
                count += 1
                self._sets[name].add(member)
        return count

    def _smembers(self, name: str) -> Set[Any]:
        """Get all set members."""
        return self._sets.get(name, set()).copy()

    def _srem(self, name: str, *members: Any) -> int:
        """Remove members from set."""
        if name not in self._sets:
            return 0
        count = 0
        for member in members:
            if member in self._sets[name]:
                count += 1
                self._sets[name].remove(member)
        return count

    def _scard(self, name: str) -> int:
        """Get set cardinality."""
        return len(self._sets.get(name, set()))

    def _sismember(self, name: str, member: Any) -> bool:
        """Check if member is in set."""
        return member in self._sets.get(name, set())

    def _zadd(self, name: str, mapping: Dict[Any, float]) -> int:
        """Add members to sorted set."""
        if name not in self._sorted_sets:
            self._sorted_sets[name] = {}
        count = 0
        for member, score in mapping.items():
            # Check if member already exists
            existed = False
            for s, members in self._sorted_sets[name].items():
                if member in members:
                    members.remove(member)
                    existed = True
                    break
            if score not in self._sorted_sets[name]:
                self._sorted_sets[name][score] = set()
            self._sorted_sets[name][score].add(member)
            if existed:
                count += 1
        return count

    def _zrange(self, name: str, start: int, end: int) -> List[Any]:
        """Get range of sorted set by score (low to high)."""
        scores = sorted(self._sorted_sets.get(name, {}).keys())
        members = []
        for score in scores[start:end+1]:
            members.extend(list(self._sorted_sets[name][score]))
        return members

    def _zrevrange(self, name: str, start: int, end: int) -> List[Any]:
        """Get range of sorted set by score (high to low)."""
        scores = sorted(self._sorted_sets.get(name, {}).keys(), reverse=True)
        members = []
        for score in scores[start:end+1]:
            members.extend(list(self._sorted_sets[name][score]))
        return members

    def _zrangebyscore(self, name: str, min_score: float, max_score: float,
                         start: int = 0, num: int = -1) -> List[Any]:
        """Get range of sorted set by score range."""
        scores = [s for s in self._sorted_sets.get(name, {}).keys()
                  if min_score <= s <= max_score]
        scores.sort()
        members = []
        for i, score in enumerate(scores):
            if i >= start and (num == -1 or len(members) < num):
                members.extend(list(self._sorted_sets[name][score]))
        return members

    def _zrevrangebyscore(self, name: str, max_score: float, min_score: float,
                            start: int = 0, num: int = -1) -> List[Any]:
        """Get range of sorted set by score range (reverse)."""
        scores = [s for s in self._sorted_sets.get(name, {}).keys()
                  if min_score <= s <= max_score]
        scores.sort(reverse=True)
        members = []
        for i, score in enumerate(scores):
            if i >= start and (num == -1 or len(members) < num):
                members.extend(list(self._sorted_sets[name][score]))
        return members

    def _zscore(self, name: str, member: Any) -> Optional[float]:
        """Get score of member in sorted set."""
        for score, members in self._sorted_sets.get(name, {}).items():
            if member in members:
                return score
        return None

    def _incr(self, key: str) -> int:
        """Increment value by 1."""
        current = int(self._get(key) or 0)
        self._set(key, current + 1)
        return current + 1

    def _incrby(self, key: str, amount: int) -> int:
        """Increment value by amount."""
        current = int(self._get(key) or 0)
        self._set(key, current + amount)
        return current + amount

    def _decr(self, key: str) -> int:
        """Decrement value by 1."""
        current = int(self._get(key) or 0)
        self._set(key, current - 1)
        return current - 1

    def _expire(self, key: str, seconds: int) -> int:
        """Set expiration time (mock)."""
        # In real Redis, this would set TTL
        # For mock, we just return 1 if key exists (in any storage)
        if key in self._storage or key in self._hashes or key in self._lists or key in self._sets or key in self._sorted_sets:
            return 1
        return 0

    def _ttl(self, key: str) -> int:
        """Get time to live (mock)."""
        # Return -1 if key exists (no expiration), -2 if not exists
        return -1 if key in self._storage else -2

    def _keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        import fnmatch
        all_keys = (
            list(self._storage.keys()) +
            list(self._hashes.keys()) +
            list(self._lists.keys()) +
            list(self._sets.keys()) +
            list(self._sorted_sets.keys())
        )
        return [k for k in set(all_keys) if fnmatch.fnmatch(k, pattern)]

    def _flushdb(self) -> bool:
        """Flush all database data."""
        self._storage.clear()
        self._hashes.clear()
        self._lists.clear()
        self._sets.clear()
        self._sorted_sets.clear()
        return True

    # Support for the 'mapping' parameter in hset (passed as positional arg by redis.py)
    def hset(self, name, *args, **kwargs):
        """Handle both mapping and key=value forms."""
        # Redis.py hset(name, mapping=...) passes mapping as keyword
        if 'mapping' in kwargs:
            return self._hset_multi(name, kwargs['mapping'])
        # Redis.py hset(name, key, value) - positional form
        elif len(args) == 2:
            return self._hset(name, args[0], args[1])
        # Redis.py hset(name, **mapping) - keyword form of mapping
        elif len(args) == 0 and 'key' in kwargs and 'value' in kwargs:
            return self._hset(name, kwargs['key'], kwargs['value'])
        # Fall back: treat kwargs as mapping
        elif kwargs:
            return self._hset_multi(name, kwargs)
        return 0

    def clear_all(self) -> None:
        """Clear all mock data."""
        self._storage.clear()
        self._hashes.clear()
        self._lists.clear()
        self._sets.clear()
        self._sorted_sets.clear()

    def debug_print(self) -> None:
        """Print current state for debugging."""
        print(f"Storage: {self._storage}")
        print(f"Hashes: {self._hashes}")
        print(f"Lists: {self._lists}")
        print(f"Sets: {self._sets}")
        print(f"SortedSets: {self._sorted_sets}")


def create_mock_redis() -> MockRedis:
    """Factory function to create a mock Redis client."""
    return MockRedis()