"""Database client utilities for Redis and storage adapters."""

import os
from typing import Optional

# Try to import redis, fall back to mock for local development
try:
    import redis
    _redis_available = True
except ImportError:
    from rpg_world_agent.data.mock_redis import MockRedis
    redis = type('Redis', (MockRedis,), {})  # Make MockRedis behave like redis.Redis
    _redis_available = False

from rpg_world_agent.config.settings import AGENT_CONFIG


class DBClient:
    """Provide singleton clients and helper methods for storage services."""

    _redis_instance = None
    _storage_adapter_instance = None

    @classmethod
    def get_redis(cls):
        """Return a singleton Redis connection (or mock for local dev)."""
        if cls._redis_instance is None:
            conf = AGENT_CONFIG["redis"]
            try:
                if not _redis_available:
                    print("⚠️  Redis module not available, using mock storage for local development")
                    cls._redis_instance = MockRedis(
                        host=conf["host"],
                        port=conf["port"],
                        db=conf["db"],
                        decode_responses=True,
                    )
                else:
                    cls._redis_instance = redis.Redis(
                        host=conf["host"],
                        port=conf["port"],
                        password=conf["password"],
                        db=conf["db"],
                        decode_responses=True,
                        socket_timeout=2,
                    )
                    cls._redis_instance.ping()
                    print("✅ Redis 连接成功")
            except Exception as exc:
                print(f"❌ Redis 连接失败: {exc}")
                print("⚠️  Using mock storage for local development")
                cls._redis_instance = MockRedis(
                    host=conf["host"],
                    port=conf["port"],
                    db=conf["db"],
                    decode_responses=True,
                )
        return cls._redis_instance

    @classmethod
    def get_storage_adapter(cls):
        """Return a singleton storage adapter (LocalFileStorage or MinIOStorage)."""
        if cls._storage_adapter_instance is None:
            from rpg_world_agent.data.storage_adapter import get_storage_adapter
            cls._storage_adapter_instance = get_storage_adapter()
        return cls._storage_adapter_instance

    @staticmethod
    def save_json(object_name: str, data) -> None:
        """Save JSON data to configured storage."""
        adapter = DBClient.get_storage_adapter()
        adapter.save_json(object_name, data)

    @staticmethod
    def load_json(object_name: str):
        """Read JSON data from configured storage."""
        adapter = DBClient.get_storage_adapter()
        return adapter.load_json(object_name)

    @staticmethod
    def delete_json(object_name: str) -> bool:
        """Delete JSON object from configured storage."""
        adapter = DBClient.get_storage_adapter()
        return adapter.delete_object(object_name)

    @staticmethod
    def list_json(prefix: str = ""):
        """List JSON objects with given prefix."""
        adapter = DBClient.get_storage_adapter()
        return adapter.list_objects(prefix)

    # Backward compatibility methods (deprecated)
    @staticmethod
    def save_json_to_minio(object_name: str, data) -> None:
        """[Deprecated] Save JSON data to storage. Use save_json instead."""
        DBClient.save_json(object_name, data)

    @staticmethod
    def load_json_from_minio(object_name: str):
        """[Deprecated] Read JSON data from storage. Use load_json instead."""
        return DBClient.load_json(object_name)
