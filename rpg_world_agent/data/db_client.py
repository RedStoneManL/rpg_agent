"""Lightweight database client placeholders for Redis and MinIO access."""

import json
from typing import Any, Dict, Optional


class MockRedis:
    """Simple in-memory Redis-like store for development and testing."""

    def __init__(self):
        self.storage: Dict[str, Any] = {}
        self.lists: Dict[str, list] = {}

    def rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)

    def lrange(self, key: str, start: int, end: int):
        items = self.lists.get(key, [])
        if end == -1:
            end = None
        else:
            end += 1
        return items[start:end]

    def expire(self, key: str, _ttl: int) -> None:
        return None

    def hset(self, key: str, mapping: Dict[str, Any]) -> None:
        self.storage.setdefault(key, {}).update(mapping)

    def hgetall(self, key: str) -> Dict[str, Any]:
        return self.storage.get(key, {})


class DBClient:
    """Facade for storage services used by the agents."""

    _redis_instance: Optional[MockRedis] = None

    @classmethod
    def get_redis(cls) -> MockRedis:
        if cls._redis_instance is None:
            cls._redis_instance = MockRedis()
        return cls._redis_instance

    @classmethod
    def save_json_to_minio(cls, object_name: str, data: Dict[str, Any]) -> None:
        with open(object_name.replace("/", "_"), "w", encoding="utf-8") as file:
            file.write(json.dumps(data, ensure_ascii=False, indent=2))
