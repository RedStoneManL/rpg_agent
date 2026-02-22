"""Mock MinIO client for testing."""

import json
import io
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class MockBucket:
    name: str
    objects: Dict[str, bytes] = None

    def __post_init__(self):
        if self.objects is None:
            self.objects = {}


@dataclass
class MockObject:
    object_name: str
    data: bytes
    size: int
    last_modified: float
    etag: str = "mock-etag"

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        pass

    def release_conn(self) -> None:
        pass


class MockMinIOClient:
    """
    In-memory mock MinIO client for testing.
    Simulates MinIO S3-compatible operations without requiring actual MinIO instance.
    """

    def __init__(self):
        self.buckets: Dict[str, MockBucket] = {}

    def make_bucket(self, bucket_name: str) -> bool:
        """Create a new bucket. Returns True if created, False if exists."""
        if bucket_name in self.buckets:
            return False  # Already exists, don't raise
        self.buckets[bucket_name] = MockBucket(name=bucket_name)
        return True

    def bucket_exists(self, bucket_name: str) -> bool:
        """Check if bucket exists."""
        return bucket_name in self.buckets

    def list_buckets(self) -> List[MockBucket]:
        """List all buckets."""
        return list(self.buckets.values())

    def remove_bucket(self, bucket_name: str) -> bool:
        """Remove a bucket."""
        if bucket_name in self.buckets:
            del self.buckets[bucket_name]
            return True
        return False

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: io.BytesIO,
        length: int,
        content_type: str = "application/octet-stream"
    ) -> None:
        """Put an object into a bucket. Creates bucket if it doesn't exist."""
        if bucket_name not in self.buckets:
            # Auto-create bucket for mock convenience
            self.buckets[bucket_name] = MockBucket(name=bucket_name)

        data.seek(0)
        object_data = data.read()
        self.buckets[bucket_name].objects[object_name] = MockObject(
            object_name=object_name,
            data=object_data,
            size=len(object_data),
            last_modified=datetime.now().timestamp()
        )

    def get_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> MockObject:
        """Get an object from a bucket."""
        if bucket_name not in self.buckets:
            raise ValueError(f"Bucket not found: {bucket_name}")

        bucket = self.buckets[bucket_name]
        if object_name not in bucket.objects:
            raise ValueError(f"Object not found: {object_name}")

        return bucket.objects[object_name]

    def remove_object(self, bucket_name: str, object_name: str) -> None:
        """Remove an object from a bucket."""
        if bucket_name in self.buckets:
            if object_name in self.buckets[bucket_name].objects:
                del self.buckets[bucket_name].objects[object_name]

    def list_objects(
        self,
        bucket_name: str,
        prefix: str = "",
        recursive: bool = False,
        start_after: str = None
    ) -> List[MockObject]:
        """List objects in a bucket."""
        if bucket_name not in self.buckets:
            raise ValueError(f"Bucket not found: {bucket_name}")

        bucket = self.buckets[bucket_name]
        objects = []

        for obj_name, obj_data in bucket.objects.items():
            # Check prefix
            if prefix and not obj_name.startswith(prefix):
                continue

            # Check recursive - if False, only return objects at this level
            if not recursive and prefix:
                relative_path = obj_name[len(prefix):]
                if "/" in relative_path:
                    continue

            # Check start_after
            if start_after and obj_name <= start_after:
                continue

            objects.append(obj_data)

        # Sort by name
        objects.sort(key=lambda x: x.object_name)
        return objects

    def stat_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> Dict[str, Any]:
        """Get object metadata."""
        obj = self.get_object(bucket_name, object_name)
        return {
            "name": obj.object_name,
            "size": obj.size,
            "last_modified": obj.last_modified,
            "etag": obj.etag
        }

    def fget_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str
    ) -> None:
        """Download object to file."""
        obj = self.get_object(bucket_name, object_name)
        with open(file_path, "wb") as f:
            f.write(obj.data)

    def fput_object(
        self,
        bucket_name: str,
        object_name: str,
        file_path: str,
        content_type: str = "application/octet-stream"
    ) -> None:
        """Upload a file."""
        with open(file_path, "rb") as f:
            data = f.read()
        self.put_object(
            bucket_name,
            object_name,
            io.BytesIO(data),
            len(data),
            content_type
        )

    # JSON convenience methods
    def put_json_object(
        self,
        bucket_name: str,
        object_name: str,
        data: Dict[str, Any]
    ) -> None:
        """Put a JSON object."""
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.put_object(bucket_name, object_name, io.BytesIO(json_bytes), len(json_bytes))

    def get_json_object(
        self,
        bucket_name: str,
        object_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get a JSON object."""
        try:
            obj = self.get_object(bucket_name, object_name)
            return json.loads(obj.data.decode("utf-8"))
        except (json.JSONDecodeError, Exception):
            return None

    def clear_all(self) -> None:
        """Clear all mock data."""
        self.buckets.clear()

    def debug_print(self) -> None:
        """Print current state for debugging."""
        for bucket_name, bucket in self.buckets.items():
            print(f"Bucket: {bucket_name}")
            for obj_name in bucket.objects:
                print(f"  - {obj_name}")


def create_mock_minio() -> MockMinIOClient:
    """Factory function to create a mock MinIO client."""
    return MockMinIOClient()