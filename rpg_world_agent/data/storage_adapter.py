"""Storage adapter interface and implementations for save data.

Supports both local file storage and MinIO S3-compatible storage.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from rpg_world_agent.config.settings import AGENT_CONFIG


class StorageAdapter(ABC):
    """Abstract base class for storage adapters."""

    @abstractmethod
    def save_json(self, object_name: str, data: Dict[str, Any]) -> None:
        """Save JSON data to storage."""
        pass

    @abstractmethod
    def load_json(self, object_name: str) -> Optional[Any]:
        """Load JSON data from storage."""
        pass

    @abstractmethod
    def delete_object(self, object_name: str) -> bool:
        """Delete an object from storage."""
        pass

    @abstractmethod
    def list_objects(self, prefix: str = "") -> List[str]:
        """List all objects with given prefix."""
        pass

    @abstractmethod
    def exists(self, object_name: str) -> bool:
        """Check if an object exists."""
        pass


class LocalFileStorage(StorageAdapter):
    """Local file system storage adapter."""

    def __init__(self, base_path: Optional[str] = None):
        """Initialize local file storage.

        Args:
            base_path: Base directory for storage. Defaults to ./saves/
        """
        if base_path is None:
            base_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "saves"
            )

        self.base_path = base_path
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure the base directory exists."""
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)
            print(f"📁 创建存档目录: {self.base_path}")

    def _get_full_path(self, object_name: str) -> str:
        """Get full file path for an object name."""
        normalized_name = object_name.replace("/", os.sep)
        return os.path.join(self.base_path, normalized_name)

    def save_json(self, object_name: str, data: Dict[str, Any]) -> None:
        """Save JSON data to local file."""
        full_path = self._get_full_path(object_name)
        dir_path = os.path.dirname(full_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_json(self, object_name: str) -> Optional[Any]:
        """Load JSON data from local file."""
        full_path = self._get_full_path(object_name)
        if not os.path.exists(full_path):
            return None
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def delete_object(self, object_name: str) -> bool:
        """Delete a file."""
        full_path = self._get_full_path(object_name)
        if not os.path.exists(full_path):
            return False
        try:
            os.remove(full_path)
            return True
        except OSError:
            return False

    def list_objects(self, prefix: str = "") -> List[str]:
        """List all files with given prefix."""
        results = []
        prefix_path = prefix.replace("/", os.sep)
        prefix_dir = os.path.dirname(prefix_path) if prefix_path else ""
        search_dir = os.path.join(self.base_path, prefix_dir) if prefix_dir else self.base_path
        if not os.path.exists(search_dir):
            return results
        for root, dirs, files in os.walk(search_dir):
            for filename in files:
                if not filename.endswith(".json"):
                    continue
                rel_path = os.path.relpath(os.path.join(root, filename), self.base_path)
                rel_path = rel_path.replace(os.sep, "/")
                if not prefix or rel_path.startswith(prefix):
                    results.append(rel_path)
        return results

    def exists(self, object_name: str) -> bool:
        """Check if a file exists."""
        full_path = self._get_full_path(object_name)
        return os.path.exists(full_path)


class MinIOStorage(StorageAdapter):
    """MinIO S3-compatible storage adapter."""

    def __init__(self):
        """Initialize MinIO storage."""
        import io
        import urllib3
        from minio import Minio
        self._BytesIO = io.BytesIO
        self._PoolManager = urllib3.PoolManager
        conf = AGENT_CONFIG["minio"]
        http_client = None
        if conf["secure"]:
            http_client = self._PoolManager(cert_reqs="CERT_NONE", assert_hostname=False)
        self.client = Minio(
            conf["endpoint"],
            access_key=conf["access_key"],
            secret_key=conf["secret_key"],
            secure=conf["secure"],
            http_client=http_client,
        )
        self.bucket_name = conf["bucket_name"]
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
        print("✅ MinIO 连接成功")

    def save_json(self, object_name: str, data: Dict[str, Any]) -> None:
        """Save JSON data to MinIO."""
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        data_stream = self._BytesIO(json_bytes)
        self.client.put_object(
            self.bucket_name,
            object_name,
            data_stream,
            len(json_bytes),
            content_type="application/json",
        )

    def load_json(self, object_name: str) -> Optional[Any]:
        """Load JSON data from MinIO."""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = json.loads(response.read().decode("utf-8"))
            response.close()
            response.release_conn()
            return data
        except Exception:
            return None

    def delete_object(self, object_name: str) -> bool:
        """Delete an object from MinIO."""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except Exception:
            return False

    def list_objects(self, prefix: str = "") -> List[str]:
        """List objects with given prefix."""
        results = []
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            for obj in objects:
                results.append(obj.object_name)
        except Exception:
            pass
        return results

    def exists(self, object_name: str) -> bool:
        """Check if an object exists."""
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except Exception:
            return False


def get_storage_adapter() -> StorageAdapter:
    """Get the appropriate storage adapter based on configuration.

    Returns:
        StorageAdapter: LocalFileStorage or MinIOStorage instance
    """
    storage_type = os.getenv("RPG_STORAGE_TYPE", "local").lower()
    if storage_type == "minio":
        return MinIOStorage()
    else:
        return LocalFileStorage()
