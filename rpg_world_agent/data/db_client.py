"""Database client providing Redis and MinIO access for the agent."""

import io
import json
from typing import Any, Dict, Optional

import redis
import urllib3
from minio import Minio

from config.settings import AGENT_CONFIG


class DBClient:
    """Lazy-initialized clients for external storage services."""

    _redis_instance: Optional[redis.Redis] = None
    _minio_instance: Optional[Minio] = None

    @classmethod
    def get_redis(cls) -> redis.Redis:
        """Return a singleton Redis client configured from ``AGENT_CONFIG``."""

        if cls._redis_instance is None:
            conf = AGENT_CONFIG["redis"]
            try:
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
            except Exception as exc:  # noqa: BLE001
                print(f"❌ Redis 连接失败: {exc}")
                raise
        return cls._redis_instance

    @classmethod
    def get_minio(cls) -> Minio:
        """Return a singleton MinIO client configured from ``AGENT_CONFIG``."""

        if cls._minio_instance is None:
            conf = AGENT_CONFIG["minio"]
            http_client = None
            if conf["secure"]:
                http_client = urllib3.PoolManager(
                    cert_reqs="CERT_NONE",
                    assert_hostname=False,
                )

            try:
                cls._minio_instance = Minio(
                    conf["endpoint"],
                    access_key=conf["access_key"],
                    secret_key=conf["secret_key"],
                    secure=conf["secure"],
                    http_client=http_client,
                )
                if not cls._minio_instance.bucket_exists(conf["bucket_name"]):
                    cls._minio_instance.make_bucket(conf["bucket_name"])
                print("✅ MinIO 连接成功")
            except Exception as exc:  # noqa: BLE001
                print(f"❌ MinIO 连接失败: {exc}")
                raise
        return cls._minio_instance

    @staticmethod
    def save_json_to_minio(object_name: str, data: Dict[str, Any]) -> None:
        """Persist JSON data to MinIO as a single object."""

        client = DBClient.get_minio()
        bucket = AGENT_CONFIG["minio"]["bucket_name"]
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        data_stream = io.BytesIO(json_bytes)
        client.put_object(
            bucket,
            object_name,
            data_stream,
            len(json_bytes),
            content_type="application/json",
        )

    @staticmethod
    def load_json_from_minio(object_name: str) -> Optional[Dict[str, Any]]:
        """Load JSON data from MinIO, returning ``None`` when missing."""

        client = DBClient.get_minio()
        bucket = AGENT_CONFIG["minio"]["bucket_name"]
        response = None
        try:
            response = client.get_object(bucket, object_name)
            data = json.loads(response.read().decode("utf-8"))
            return data
        except Exception:  # noqa: BLE001
            return None
        finally:
            if response is not None:
                response.close()
                response.release_conn()
