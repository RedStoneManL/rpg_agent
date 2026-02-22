"""
Unit tests for CognitionSystem.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from typing import Generator, TYPE_CHECKING

from tests.mocks.redis_mock import MockRedis, create_mock_redis
from tests.mocks.minio_mock import MockMinIOClient, create_mock_minio

# Import actual type for runtime
from rpg_world_agent.core.cognition import CognitionSystem


@pytest.mark.unit
class TestCognitionMessageHistory:
    """Tests for conversation history management."""

    def test_add_message_stores_in_redis(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that add_message stores message in Redis list."""
        cognition_system.add_message("user", "Hello, world!")

        history_key = "rpg:history:test_session_001"
        messages = mock_redis.lrange(history_key, 0, -1)

        assert len(messages) == 1
        stored_msg = json.loads(messages[0])
        assert stored_msg["role"] == "user"
        assert stored_msg["content"] == "Hello, world!"

    def test_add_multiple_messages(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that multiple messages are stored in order."""
        cognition_system.add_message("user", "First message")
        cognition_system.add_message("assistant", "First response")
        cognition_system.add_message("user", "Second message")

        history_key = "rpg:history:test_session_001"
        messages = [json.loads(m) for m in mock_redis.lrange(history_key, 0, -1)]

        assert len(messages) == 3
        assert messages[0]["content"] == "First message"
        assert messages[1]["content"] == "First response"
        assert messages[2]["content"] == "Second message"

    def test_get_recent_history_returns_limit(self, cognition_system: CognitionSystem):
        """Test that get_recent_history returns at most limit messages."""
        for i in range(10):
            cognition_system.add_message("user", f"Message {i}")

        recent = cognition_system.get_recent_history(limit=5)

        assert len(recent) == 5
        assert recent[-1]["content"] == "Message 9"
        assert recent[0]["content"] == "Message 5"

    def test_get_all_history_returns_all(self, cognition_system: CognitionSystem):
        """Test that get_all_history returns complete conversation history."""
        for i in range(5):
            cognition_system.add_message("user", f"Message {i}")

        all_history = cognition_system.get_all_history()

        assert len(all_history) == 5
        for i, msg in enumerate(all_history):
            assert msg["content"] == f"Message {i}"

    def test_get_all_history_returns_most_recent_first(self, cognition_system: CognitionSystem):
        """Test that get_all_history returns messages in chronological order."""
        cognition_system.add_message("user", "First")
        cognition_system.add_message("assistant", "Response")
        cognition_system.add_message("user", "Second")

        history = cognition_system.get_all_history()

        assert history[0]["content"] == "First"
        assert history[1]["content"] == "Response"
        assert history[2]["content"] == "Second"

    def test_get_recent_history_empty_for_new_session(self, cognition_system: CognitionSystem):
        """Test that get_recent_history returns empty list for new session."""
        history = cognition_system.get_recent_history()
        assert history == []


@pytest.mark.unit
class TestCognitionPlayerState:
    """Tests for player state management."""

    def test_update_player_state_stores_simple_values(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that update_player_state stores simple field values."""
        updates = {
            "hp": 95,
            "sanity": 90,
            "location": "loc_forest"
        }

        cognition_system.update_player_state(updates)

        state_key = "rpg:state:test_session_001"
        assert mock_redis.hget(state_key, "hp") == "95"
        assert mock_redis.hget(state_key, "sanity") == "90"
        assert mock_redis.hget(state_key, "location") == "loc_forest"

    def test_update_player_state_serializes_complex_fields(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that complex fields (dict, list) are JSON serialized."""
        attributes = {"STR": 12, "DEX": 10, "INT": 14}
        skills = ["observation", "stealth", "perception"]

        cognition_system.update_player_state({
            "attributes": attributes,
            "skills": skills
        })

        state_key = "rpg:state:test_session_001"
        attrs_raw = mock_redis.hget(state_key, "attributes")
        skills_raw = mock_redis.hget(state_key, "skills")

        assert json.loads(attrs_raw) == attributes
        assert json.loads(skills_raw) == skills

    def test_get_player_state_returns_all_fields(self, cognition_system: CognitionSystem):
        """Test that get_player_state returns complete state."""
        test_state = {
            "hp": 100,
            "max_hp": 100,
            "sanity": 95,
            "max_sanity": 100,
            "location": "loc_tavern",
            "level": 2,
            "exp": 250,
            "gold": 50
        }

        # Manually set using redis to avoid serialization
        self._set_state_directly(cognition_system, test_state)

        state = cognition_system.get_player_state()

        for key, value in test_state.items():
            assert state[key] == value

    def test_get_player_state_deserializes_complex_fields(self, cognition_system: CognitionSystem):
        """Test that get_player_state deserializes dict/list fields."""
        test_attributes = {"STR": 15, "DEX": 11}
        test_skills = ["combat", "athletics"]

        updates = {
            "attributes": test_attributes,
            "skills": test_skills
        }
        cognition_system.update_player_state(updates)

        state = cognition_system.get_player_state()

        assert isinstance(state["attributes"], dict)
        assert state["attributes"] == test_attributes
        assert isinstance(state["skills"], list)
        assert state["skills"] == test_skills

    def test_get_player_state_handles_corrupted_json(self, cognition_system: CognitionSystem):
        """Test that get_player_state handles corrupted JSON gracefully."""
        # Set invalid JSON
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "hp": "100",
            "attributes": "{invalid json"
        }

        with patch.object(cognition_system, 'redis', mock_redis):
            state = cognition_system.get_player_state()
            # Should return valid fields (hp is converted to int)
            assert state.get("hp") == 100
            # Corrupted field should be handled (either skipped or returned as-is)
            # attributes should not be converted since it's invalid JSON

    def _set_state_directly(self, cognition: CognitionSystem, state_dict: dict):
        """Helper to set state directly in Redis."""
        for key, value in state_dict.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            else:
                value = str(value)
            cognition.redis.hset(f"rpg:state:{cognition.session_id}", key, value)


@pytest.mark.unit
class TestCognitionSaveLoad:
    """Tests for session save/load functionality."""

    def test_archive_session_saves_to_minio(self, cognition_system: CognitionSystem, mock_minio: MockMinIOClient):
        """Test that archive_session saves data to MinIO."""
        # Add some test data
        cognition_system.add_message("user", "Test input")
        cognition_system.add_message("assistant", "Test response")

        with patch('rpg_world_agent.data.db_client.DBClient._minio_instance', mock_minio):
            with patch('rpg_world_agent.core.cognition.AGENT_CONFIG', {
                "minio": {"bucket_name": "rpg-world-data"}
            }):
                # Mock save_json_to_minio
                from rpg_world_agent.data.db_client import DBClient
                original_save = DBClient.save_json_to_minio
                saved_data = {}

                def mock_save_json(name, data):
                    saved_data["name"] = name
                    saved_data["data"] = data

                with patch.object(DBClient, 'save_json_to_minio', mock_save_json):
                    object_name = cognition_system.archive_session()

        assert object_name == "saves/test_session_001.json"
        assert saved_data["name"] == "saves/test_session_001.json"
        assert saved_data["data"]["session_id"] == "test_session_001"

    def test_load_session_restores_history(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that load_session restores conversation history."""
        save_data = {
            "history": [
                {"role": "user", "content": "Restored message 1"},
                {"role": "assistant", "content": "Restored response 1"}
            ],
            "final_state": {"hp": 90},
            "metadata": {"session_id": "test_session_001"}
        }

        # Patch load_json_from_minio to return our test data
        from rpg_world_agent.data.db_client import DBClient
        with patch.object(DBClient, 'load_json_from_minio', return_value=save_data):
            success = cognition_system.load_session()

        assert success is True
        history = cognition_system.get_all_history()
        assert len(history) == 2
        assert history[0]["content"] == "Restored message 1"

    def test_load_session_restores_player_state(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that load_session restores player state."""
        test_state = {
            "hp": 75,
            "max_hp": 100,
            "sanity": 80,
            "location": "loc_ruins"
        }

        save_data = {
            "history": [],
            "final_state": test_state,
            "metadata": {"session_id": "test_session_001"}
        }

        # Patch load_json_from_minio to return our test data
        from rpg_world_agent.data.db_client import DBClient
        with patch.object(DBClient, 'load_json_from_minio', return_value=save_data):
            cognition_system.load_session()

        state = cognition_system.get_player_state()
        assert state["hp"] == 75
        assert state["location"] == "loc_ruins"

    def test_load_session_returns_false_for_nonexistent_save(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that load_session returns False when save doesn't exist."""
        # Patch load_json_from_minio to return None
        from rpg_world_agent.data.db_client import DBClient
        with patch.object(DBClient, 'load_json_from_minio', return_value=None):
            success = cognition_system.load_session()

        assert success is False

    def test_load_session_handles_corrupted_save(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that load_session handles corrupted save file."""
        # Patch load_json_from_minio to raise an exception
        from rpg_world_agent.data.db_client import DBClient
        with patch.object(DBClient, 'load_json_from_minio', side_effect=Exception("Corrupted data")):
            success = cognition_system.load_session()

        assert success is False


@pytest.mark.unit
class TestCognitionListSaves:
    """Tests for listing available saves."""

    def test_list_saves_returns_metadata(self, mock_minio: MockMinIOClient):
        """Test that list_saves returns save metadata."""
        save_data1 = {
            "metadata": {
                "session_id": "session_001",
                "timestamp": "2025-02-10T10:00:00",
                "playtime_minutes": 15,
                "location": "loc_tavern",
                "hp": 100
            },
            "final_state": {"hp": 100}
        }
        save_data2 = {
            "metadata": {
                "session_id": "session_002",
                "timestamp": "2025-02-10T11:00:00",
                "playtime_minutes": 30,
                "location": "loc_forest",
                "hp": 85
            },
            "final_state": {"hp": 85, "sanity": 90}
        }

        from rpg_world_agent.data.db_client import DBClient
        from tests.mocks.minio_mock import MockObject
        from datetime import datetime

        # Create mock objects
        obj1 = MockObject(
            object_name="saves/session_001.json",
            data=bytearray(),
            size=0,
            last_modified=datetime.now().timestamp()
        )
        obj2 = MockObject(
            object_name="saves/session_002.json",
            data=bytearray(),
            size=0,
            last_modified=datetime.now().timestamp()
        )

        # Patch both list_objects and load_json_from_minio
        load_calls = []
        def mock_load_json(name):
            load_calls.append(name)
            if "session_001" in name:
                return save_data1
            elif "session_002" in name:
                return save_data2
            return None

        with patch.object(DBClient, 'load_json_from_minio', side_effect=mock_load_json):
            with patch('rpg_world_agent.core.cognition.AGENT_CONFIG', {
                "minio": {"bucket_name": "rpg-world-data"}
            }):
                # Also need to patch the minio instance's list_objects
                with patch.object(mock_minio, 'list_objects', return_value=[obj1, obj2]):
                    saves = CognitionSystem.list_saves()

        assert len(saves) == 2
        assert saves[0]["session_id"] == "session_001"
        assert saves[1]["session_id"] == "session_002"

    def test_list_saves_handles_empty_bucket(self, mock_minio: MockMinIOClient):
        """Test that list_saves returns empty list for empty bucket."""
        from rpg_world_agent.data.db_client import DBClient
        with patch.object(mock_minio, 'list_objects', return_value=[]):
            with patch('rpg_world_agent.core.cognition.AGENT_CONFIG', {
                "minio": {"bucket_name": "rpg-world-data"}
            }):
                with patch.object(DBClient, '_minio_instance', mock_minio):
                    saves = CognitionSystem.list_saves()

        assert saves == []


@pytest.mark.unit
class TestCognitionDeleteSave:
    """Tests for deleting saves."""

    def test_delete_save_removes_from_minio(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that delete_save removes save file from MinIO."""
        from rpg_world_agent.data.db_client import DBClient

        # Track if remove_object was called
        removed_objects = []

        def mock_remove(bucket, obj_name):
            removed_objects.append((bucket, obj_name))

        with patch.object(DBClient, '_minio_instance', mock_minio=MagicMock()):
            with patch.object(DBClient._minio_instance, 'remove_object', side_effect=mock_remove):
                with patch('rpg_world_agent.core.cognition.AGENT_CONFIG', {
                    "minio": {"bucket_name": "test-bucket"}
                }):
                    success = cognition_system.delete_save()

        assert success is True
        assert len(removed_objects) == 1
        assert removed_objects[0][1] == "saves/test_session_001.json"

    def test_delete_save_returns_false_for_nonexistent(self, cognition_system: CognitionSystem):
        """Test that delete_save returns False when save doesn't exist."""
        from rpg_world_agent.data.db_client import DBClient
        from minio.error import S3Error

        # Make remove_object raise an S3Error
        def mock_remove_error(*args, **kwargs):
            raise S3Error(
                code="NoSuchKey",
                message="The specified key does not exist",
                resource="saves/test_session_001.json",
                request_id="test-request-id",
                host_id="test-host-id",
            )

        with patch.object(DBClient, '_minio_instance', mock_minio=MagicMock()):
            with patch.object(DBClient._minio_instance, 'remove_object', side_effect=mock_remove_error):
                with patch('rpg_world_agent.core.cognition.AGENT_CONFIG', {
                    "minio": {"bucket_name": "test-bucket"}
                }):
                    success = cognition_system.delete_save()

        assert success is False


@pytest.mark.unit
class TestCognitionClearSession:
    """Tests for clearing session data."""

    def test_clear_session_removes_redis_data(self, cognition_system: CognitionSystem, mock_redis: MockRedis):
        """Test that clear_session removes all session data from Redis."""
        # Add some data
        cognition_system.add_message("user", "Test")

        # Clear session
        cognition_system.clear_session()

        history_key = "rpg:history:test_session_001"
        state_key = "rpg:state:test_session_001"
        meta_key = "rpg:meta:test_session_001"

        # exists returns int count, not boolean
        assert mock_redis.exists(history_key) == 0
        assert mock_redis.exists(state_key) == 0
        assert mock_redis.exists(meta_key) == 0


@pytest.mark.unit
class TestCognitionSessionMetadata:
    """Tests for session metadata management."""

    def test_metadata_includes_playtime(self, cognition_system: CognitionSystem):
        """Test that metadata tracks playtime correctly."""
        # First archive - just verify the function doesn't crash
        cognition_system.add_message("user", "Start")

        from rpg_world_agent.data.db_client import DBClient
        saved_data = {}

        def mock_save_json(name, data):
            saved_data["data"] = data

        with patch.object(DBClient, 'save_json_to_minio', side_effect=mock_save_json):
            with patch('rpg_world_agent.core.cognition.AGENT_CONFIG', {
                "minio": {"bucket_name": "test-bucket"}
            }):
                object_name = cognition_system.archive_session()

        # Verify the data structure
        assert "metadata" in saved_data["data"]
        assert "playtime_minutes" in saved_data["data"]["metadata"]
        assert saved_data["data"]["metadata"]["playtime_minutes"] >= 1