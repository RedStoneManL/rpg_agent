"""
Unit tests for DBClient - Redis and MinIO singleton clients.
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from tests.mocks.redis_mock import MockRedis, create_mock_redis
from tests.mocks.minio_mock import MockMinIOClient, create_mock_minio


class TestRedisSingleton:
    """Tests for Redis singleton pattern."""

    def test_redis_singleton_returns_same_instance(self):
        """Test that get_redis returns the same instance."""
        from rpg_world_agent.data.db_client import DBClient

        # Reset singleton
        DBClient._redis_instance = None

        with patch('rpg_world_agent.data.db_client.redis.Redis') as mock_redis_class:
            mock_redis = MagicMock()
            mock_redis_class.return_value = mock_redis
            mock_redis.ping.return_value = True

            instance1 = DBClient.get_redis()
            instance2 = DBClient.get_redis()

            assert instance1 is instance2
            mock_redis_class.assert_called_once()

    def test_redis_initialization_fails_on_connection_error(self):
        """Test that Redis initialization raises error on connection failure."""
        from rpg_world_agent.data.db_client import DBClient
        from redis.exceptions import ConnectionError

        # Reset singleton
        DBClient._redis_instance = None

        with patch('rpg_world_agent.data.db_client.redis.Redis') as mock_redis_class:
            mock_redis_class.side_effect = ConnectionError("Connection failed")

            with pytest.raises(ConnectionError):
                DBClient.get_redis()

    def test_redis_config_uses_agent_config(self):
        """Test that Redis connection uses AGENT_CONFIG values."""
        from rpg_world_agent.data.db_client import DBClient

        # Reset singleton
        DBClient._redis_instance = None

        test_config = {
            "redis": {
                "host": "testhost",
                "port": 1234,
                "password": "testpass",
                "db": 5,
                "ttl": 7200
            }
        }

        with patch('rpg_world_agent.data.db_client.AGENT_CONFIG', test_config):
            with patch('rpg_world_agent.data.db_client.redis.Redis') as mock_redis_class:
                mock_redis_instance = MagicMock()
                mock_redis_instance.ping.return_value = True
                mock_redis_class.return_value = mock_redis_instance

                DBClient.get_redis()

                mock_redis_class.assert_called_once_with(
                    host="testhost",
                    port=1234,
                    password="testpass",
                    db=5,
                    decode_responses=True,
                    socket_timeout=2,
                )
        # Reset singleton
        DBClient._redis_instance = None


class TestMinIOSingleton:
    """Tests for MinIO singleton pattern."""

    def test_minio_singleton_returns_same_instance(self):
        """Test that get_minio returns the same instance."""
        from rpg_world_agent.data.db_client import DBClient

        # Reset singleton
        DBClient._minio_instance = None

        with patch('rpg_world_agent.data.db_client.Minio') as mock_minio_class:
            mock_minio = MagicMock()
            mock_minio.bucket_exists.return_value = False
            mock_minio_class.return_value = mock_minio

            instance1 = DBClient.get_minio()
            instance2 = DBClient.get_minio()

            assert instance1 is instance2
            mock_minio_class.assert_called_once()

    def test_minio_creates_bucket_if_not_exists(self):
        """Test that MinIO creates bucket if it doesn't exist."""
        from rpg_world_agent.data.db_client import DBClient

        # Reset singleton
        DBClient._minio_instance = None

        test_config = {
            "minio": {
                "endpoint": "localhost:9000",
                "access_key": "test",
                "secret_key": "test",
                "secure": False,
                "bucket_name": "test-bucket"
            }
        }

        with patch('rpg_world_agent.data.db_client.AGENT_CONFIG', test_config):
            with patch('rpg_world_agent.data.db_client.Minio') as mock_minio_class:
                mock_minio = MagicMock()
                mock_minio.bucket_exists.return_value = False
                mock_minio_class.return_value = mock_minio

                DBClient.get_minio()

                mock_minio.make_bucket.assert_called_once_with("test-bucket")
        # Reset singleton
        DBClient._minio_instance = None

    def test_minio_does_not_create_bucket_if_exists(self):
        """Test that MinIO doesn't create bucket if it already exists."""
        from rpg_world_agent.data.db_client import DBClient

        # Reset singleton
        DBClient._minio_instance = None

        test_config = {
            "minio": {
                "endpoint": "localhost:9000",
                "access_key": "test",
                "secret_key": "test",
                "secure": False,
                "bucket_name": "test-bucket"
            }
        }

        with patch('rpg_world_agent.data.db_client.AGENT_CONFIG', test_config):
            with patch('rpg_world_agent.data.db_client.Minio') as mock_minio_class:
                mock_minio = MagicMock()
                mock_minio.bucket_exists.return_value = True
                mock_minio_class.return_value = mock_minio

                DBClient.get_minio()

                mock_minio.make_bucket.assert_not_called()
        # Reset singleton
        DBClient._minio_instance = None

    def test_minio_initialization_fails_on_connection_error(self):
        """Test that MinIO initialization raises error on connection failure."""
        from rpg_world_agent.data.db_client import DBClient
        from minio.error import S3Error

        # Reset singleton
        DBClient._minio_instance = None

        with patch('rpg_world_agent.data.db_client.Minio') as mock_minio_class:
            mock_minio_class.side_effect = S3Error(
                code="ConnectionError",
                message="Connection failed",
                resource="minio",
                request_id="",
                host_id="",
            )

            with pytest.raises(S3Error):
                DBClient.get_minio()


class TestMinIOJSONOperations:
    """Tests for MinIO JSON save/load helper methods."""

    def test_save_json_to_minio(self):
        """Test saving JSON data to MinIO."""
        from rpg_world_agent.data.db_client import DBClient

        test_data = {"key": "value", "number": 42}
        object_name = "test/data.json"

        with patch.object(DBClient, 'get_minio') as mock_get_minio:
            mock_minio = create_mock_minio()
            mock_minio.make_bucket("test-bucket")
            mock_get_minio.return_value = mock_minio

            with patch('rpg_world_agent.data.db_client.AGENT_CONFIG', {
                "minio": {"bucket_name": "test-bucket"}
            }):
                DBClient.save_json_to_minio(object_name, test_data)

                # Verify data was saved
                loaded = mock_minio.get_json_object("test-bucket", object_name)
                assert loaded == test_data

    def test_load_json_from_minio(self):
        """Test loading JSON data from MinIO."""
        from rpg_world_agent.data.db_client import DBClient

        test_data = {"key": "value", "number": 42}
        object_name = "test/data.json"

        with patch.object(DBClient, 'get_minio') as mock_get_minio:
            mock_minio = create_mock_minio()
            mock_minio.make_bucket("test-bucket")
            mock_minio.put_json_object("test-bucket", object_name, test_data)
            mock_get_minio.return_value = mock_minio

            with patch('rpg_world_agent.data.db_client.AGENT_CONFIG', {
                "minio": {"bucket_name": "test-bucket"}
            }):
                loaded = DBClient.load_json_from_minio(object_name)

                assert loaded == test_data

    def test_load_json_from_minio_returns_none_for_nonexistent(self):
        """Test that load_json_from_minio returns None for nonexistent objects."""
        from rpg_world_agent.data.db_client import DBClient

        with patch.object(DBClient, 'get_minio') as mock_get_minio:
            mock_minio = create_mock_minio()
            mock_minio.make_bucket("test-bucket")
            mock_get_minio.return_value = mock_minio

            with patch('rpg_world_agent.data.db_client.AGENT_CONFIG', {
                "minio": {"bucket_name": "test-bucket"}
            }):
                result = DBClient.load_json_from_minio("nonexistent.json")

                assert result is None

    def test_json_roundtrip_preserves_data(self):
        """Test that save/load roundtrip preserves all data."""
        from rpg_world_agent.data.db_client import DBClient

        test_data = {
            "string": "test",
            "number": 123,
            "float": 45.67,
            "boolean": True,
            "null": None,
            "nested": {"key": "value"},
            "array": [1, 2, 3],
            "unicode": "你好世界"
        }
        object_name = "test/roundtrip.json"

        with patch.object(DBClient, 'get_minio') as mock_get_minio:
            mock_minio = create_mock_minio()
            mock_minio.make_bucket("test-bucket")
            mock_get_minio.return_value = mock_minio

            with patch('rpg_world_agent.data.db_client.AGENT_CONFIG', {
                "minio": {"bucket_name": "test-bucket"}
            }):
                DBClient.save_json_to_minio(object_name, test_data)
                loaded = DBClient.load_json_from_minio(object_name)

                assert loaded == test_data


@pytest.mark.unit
class TestEnvironmentVariableOverrides:
    """Tests for environment variable configuration overrides."""

    def test_environment_variable_override(self, monkeypatch, env_var, config_key, value):
        """Test that environment variables override config values."""
        from rpg_world_agent.data.db_client import DBClient
        from rpg_world_agent.config import settings

        monkeypatch.setenv(env_var, str(value))

        # Reload config to pick up env vars
        import importlib
        importlib.reload(settings)

        # Navigate to nested config
        config_value = settings.AGENT_CONFIG
        for key in config_key[:-1]:
            config_value = config_value[key]
        assert config_value[config_key[-1]] == value

        # Cleanup
        monkeypatch.delenv(env_var)
        importlib.reload(settings)
        try:
            DBClient._redis_instance = None
            DBClient._minio_instance = None
        except AttributeError:
            # DBClient might not be imported yet
            pass

    @pytest.mark.parametrize("env_var,config_key,value", [
        ("RPG_REDIS_HOST", ["redis", "host"], "custom-host"),
        ("RPG_REDIS_PORT", ["redis", "port"], 9999),
        ("RPG_MINIO_ENDPOINT", ["minio", "endpoint"], "custom-endpoint:9000"),
        ("RPG_LLM_BASE_URL", ["llm", "base_url"], "http://custom-llm/v1"),
    ])