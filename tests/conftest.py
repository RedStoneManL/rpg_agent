"""
Pytest configuration and fixtures for RPG game engine tests.
"""

import json
import sys
import os
from typing import Dict, Any, Generator
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import after path setup
from tests.mocks.llm_mock import (
    MockLLMClient,
    create_mock_llm_client,
    MOCK_INTENT_EXPLORE,
    MOCK_INTENT_ACTION,
    MOCK_INTENT_CHAT,
    MOCK_ROUTE_CONCEPT,
    MOCK_DYNAMIC_LOCATION,
    MOCK_NARRATIVE
)
from tests.mocks.redis_mock import MockRedis, create_mock_redis
from tests.mocks.minio_mock import MockMinIOClient, create_mock_minio

# Import project modules
from rpg_world_agent.core.cognition import CognitionSystem
from rpg_world_agent.core.map_engine import MapTopologyEngine
from rpg_world_agent.core.event_system import (
    EventSystem,
    EventData,
    EventType,
    EventPriority
)
from rpg_world_agent.core.player_character import PlayerCharacter
from rpg_world_agent.core.world_state import WorldStateManager
from rpg_world_agent.core.context_loader import ContextLoader
from rpg_world_agent.core.plugin_system import PluginManager
from rpg_world_agent.core.runtime import RuntimeEngine
from rpg_world_agent.data.llm_client import LLMClientFactory


# ============================================================================
# Redis Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_redis() -> Generator[MockRedis, None, None]:
    """Create a fresh MockRedis instance for each test."""
    redis = create_mock_redis()
    yield redis
    redis.clear_all()


@pytest.fixture
def mock_redis_with_data(mock_redis: MockRedis) -> MockRedis:
    """MockRedis with sample data already loaded."""
    # Sample node data
    mock_redis.set(
        "rpg:map:node:loc_tavern",
        json.dumps({
            "node_id": "loc_tavern",
            "name": "Dusty Tavern",
            "desc": "A dimly lit tavern with dusty tables.",
            "geo_feature": "Building",
            "type": "L2",
            "risk_level": 1
        }, ensure_ascii=False)
    )

    mock_redis.set(
        "rpg:map:node:loc_forest",
        json.dumps({
            "node_id": "loc_forest",
            "name": "Dark Forest",
            "desc": "A forest with tall, dark trees.",
            "geo_feature": "Forest",
            "type": "L2",
            "risk_level": 2
        }, ensure_ascii=False)
    )

    # Sample edge data
    edge_tavern = json.dumps({
        "target_id": "loc_forest",
        "type": "Travel",
        "route_info": {
            "route_name": "Muddy Path",
            "description": "A muddy path through the woods.",
            "risk_level": 1
        }
    }, ensure_ascii=False)
    mock_redis.hset("rpg:map:edges:loc_tavern", "Travel:loc_forest", edge_tavern)

    edge_forest = json.dumps({
        "target_id": "loc_tavern",
        "type": "Travel",
        "route_info": {
            "route_name": "Muddy Path",
            "description": "A muddy path through the woods.",
            "risk_level": 1
        }
    }, ensure_ascii=False)
    mock_redis.hset("rpg:map:edges:loc_forest", "Travel:loc_tavern", edge_forest)

    return mock_redis


# ============================================================================
# MinIO Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_minio() -> Generator[MockMinIOClient, None, None]:
    """Create a fresh MockMinIOClient instance for each test."""
    minio = create_mock_minio()
    yield minio
    minio.clear_all()


@pytest.fixture
def mock_minio_with_data(mock_minio: MockMinIOClient) -> MockMinIOClient:
    """MockMinIOClient with sample save data already loaded."""
    # Create bucket
    mock_minio.make_bucket("rpg-world-data")

    # Sample save data
    save_data = {
        "session_id": "test_session_001",
        "metadata": {
            "session_id": "test_session_001",
            "timestamp": "2025-02-10T10:00:00",
            "playtime_minutes": 5,
            "location": "loc_tavern",
            "hp": 100,
            "sanity": 100
        },
        "history": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Welcome!"}
        ],
        "final_state": {
            "hp": 95,
            "max_hp": 100,
            "sanity": 98,
            "max_sanity": 100,
            "location": "loc_tavern"
        }
    }
    mock_minio.put_json_object("rpg-world-data", "saves/test_session_001.json", save_data)

    return mock_minio


# ============================================================================
# LLM Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_llm() -> Generator[MockLLMClient, None, None]:
    """Create a fresh MockLLMClient instance for each test."""
    llm = create_mock_llm_client()
    yield llm
    llm.reset()


@pytest.fixture
def mock_llm_with_responses(mock_llm: MockLLMClient) -> MockLLMClient:
    """MockLLMClient with pre-configured responses."""
    mock_llm.set_response("intent", MOCK_INTENT_CHAT)
    mock_llm.set_response("EXPLORE", MOCK_INTENT_EXPLORE)
    mock_llm.set_response("ACTION", MOCK_INTENT_ACTION)
    mock_llm.set_response("route concept", MOCK_ROUTE_CONCEPT)
    mock_llm.set_response("dynamic sub location", MOCK_DYNAMIC_LOCATION)
    mock_llm.set_response("narrative", MOCK_NARRATIVE)
    return mock_llm


# ============================================================================
# Data Fixtures
# ============================================================================

@pytest.fixture
def sample_node_data() -> Dict[str, Any]:
    """Sample map node data."""
    return {
        "node_id": "loc_tavern",
        "name": "Dusty Tavern",
        "desc": "A dimly lit tavern with dusty tables and flickering candles.",
        "geo_feature": "Building",
        "type": "L2",
        "risk_level": 1
    }


@pytest.fixture
def sample_player_state() -> Dict[str, Any]:
    """Sample player state."""
    return {
        "hp": 100,
        "max_hp": 100,
        "sanity": 100,
        "max_sanity": 100,
        "location": "loc_tavern",
        "tags": ["traveler", "outsider"],
        "skills": ["observation", "survival"],
        "level": 1,
        "exp": 0,
        "gold": 100,
        "attributes": {
            "STR": 12,
            "DEX": 10,
            "INT": 14,
            "WIS": 13,
            "CON": 11,
            "CHA": 9
        },
        "inventory": ["rusty dagger", "leather armor"],
        "quests": []
    }


@pytest.fixture
def sample_event_data() -> Dict[str, Any]:
    """Sample event data."""
    return {
        "description": "Player discovered a hidden door",
        "target": "secret_room",
        "result": "success"
    }


@pytest.fixture
def world_config() -> Dict[str, Any]:
    """Sample world configuration."""
    return {
        "genre": "Cyberpunk/Lovecraftian",
        "tone": "Dark & Gritty",
        "final_conflict": "The Awakening of the Old Ones",
        "power_level": "adventuring"
    }


@pytest.fixture
def sample_regions() -> list:
    """Sample generated regions for map ingestion."""
    return [
        {
            "region_id": "loc_tavern",
            "name": "Dusty Tavern",
            "desc": "A dimly lit tavern.",
            "geo_feature": "Building",
            "risk_level": 1,
            "neighbors": ["loc_forest"]
        },
        {
            "region_id": "loc_forest",
            "name": "Dark Forest",
            "desc": "A forest with tall, dark trees.",
            "geo_feature": "Forest",
            "risk_level": 2,
            "neighbors": ["loc_tavern"]
        }
    ]


# ============================================================================
# DBClient Patching Fixtures
# ============================================================================

@pytest.fixture
def mock_db_client(mock_redis: MockRedis, mock_minio: MockMinIOClient):
    """Patches DBClient to return mock Redis and MinIO clients."""
    with patch('rpg_world_agent.data.db_client.DBClient._redis_instance', mock_redis), \
         patch('rpg_world_agent.data.db_client.DBClient._minio_instance', mock_minio):
        yield


# ============================================================================
# Core System Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_client_factory(mock_llm: MockLLMClient):
    """Patches LLMClientFactory to return mock client."""
    with patch.object(LLMClientFactory, 'get_client', return_value=mock_llm):
        yield mock_llm


@pytest.fixture
def cognition_system(mock_db_client) -> Generator[CognitionSystem, None, None]:
    """Create a CognitionSystem instance with mocked storage."""
    system = CognitionSystem("test_session_001")
    yield system
    # Cleanup
    system.clear_session()


@pytest.fixture
def map_engine(mock_db_client, mock_llm_client: MockLLMClient) -> MapTopologyEngine:
    """Create a MapTopologyEngine instance with mocked storage and LLM."""
    engine = MapTopologyEngine(mock_llm_client)
    return engine


@pytest.fixture
def event_system(mock_db_client) -> EventSystem:
    """Create an EventSystem instance with mocked storage."""
    return EventSystem("test_session_001")


@pytest.fixture
def world_state_manager(mock_db_client) -> WorldStateManager:
    """Create a WorldStateManager instance with mocked storage."""
    return WorldStateManager("test_session_001")


@pytest.fixture
def context_loader(mock_db_client) -> ContextLoader:
    """Create a ContextLoader instance with mocked storage."""
    return ContextLoader("test_session_001")


@pytest.fixture
def player_character() -> PlayerCharacter:
    """Create a PlayerCharacter instance."""
    return PlayerCharacter(
        name="TestHero",
        strength=12,
        dexterity=10,
        intelligence=14,
        wisdom=13,
        constitution=11,
        charisma=9
    )


# ============================================================================
# Integration Fixtures
# ============================================================================

@pytest.fixture
def empty_runtime_engine(
    mock_db_client,
    mock_llm_client: MockLLMClient
) -> RuntimeEngine:
    """Create a RuntimeEngine instance without player initialization."""
    engine = RuntimeEngine("test_session_001", llm_client=mock_llm_client)
    return engine


@pytest.fixture
def runtime_engine_with_player(
    empty_runtime_engine: RuntimeEngine,
    sample_player_state: Dict[str, Any]
) -> RuntimeEngine:
    """Create a RuntimeEngine instance with initialized player."""
    engine = empty_runtime_engine
    engine.initialize_player("loc_tavern", ["traveler", "outsider"])
    return engine


@pytest.fixture
def runtime_engine_with_map(
    mock_db_client,
    mock_llm_client: MockLLMClient,
    mock_redis_with_data: MockRedis
) -> RuntimeEngine:
    """Create a RuntimeEngine with both player and map initialized."""
    engine = RuntimeEngine("test_session_001", llm_client=mock_llm_client)
    engine.initialize_player("loc_tavern", ["traveler"])
    return engine


# ============================================================================
# Plugin Fixtures
# ============================================================================

@pytest.fixture
def clean_plugin_manager():
    """Create a clean PluginManager instance after reset."""
    PluginManager._instance = None
    manager = PluginManager.get_instance()
    yield manager
    PluginManager._instance = None


@pytest.fixture
def sample_plugin():
    """Sample plugin metadata for testing."""
    return {
        "name": "test_plugin",
        "version": "1.0.0",
        "author": "Test Author",
        "description": "A test plugin for unit testing",
        "provides_commands": ["/testcmd"],
        "provides_hooks": ["ON_TURN_START"],
        "enabled": True
    }


# ============================================================================
# Session Fixtures
# ============================================================================

@pytest.fixture
def empty_session() -> Dict[str, Any]:
    """Empty session data."""
    return {
        "session_id": "empty_session",
        "metadata": {},
        "history": [],
        "final_state": {}
    }


@pytest.fixture
def populated_session(sample_player_state: Dict[str, Any]) -> Dict[str, Any]:
    """Populated session data for testing."""
    return {
        "session_id": "populated_session",
        "metadata": {
            "session_id": "populated_session",
            "timestamp": "2025-02-10T10:00:00",
            "playtime_minutes": 10,
            "location": "loc_tavern",
            "hp": 100,
            "sanity": 100
        },
        "history": [
            {"role": "user", "content": "/look"},
            {"role": "assistant", "content": "You see: A dusty tavern with flickering candles."}
        ],
        "final_state": sample_player_state
    }


# ============================================================================
# Config Patches
# ============================================================================

@pytest.fixture
def mock_config():
    """Patch AGENT_CONFIG with test values."""
    original_config = None

    # Import config
    from rpg_world_agent.config import settings
    original_config = settings.AGENT_CONFIG.copy()

    # Set test config
    test_config = {
        "genre": "Test Genre",
        "tone": "Test Tone",
        "final_conflict": "Test Crisis",
        "llm": {
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "model": "test-model",
            "temperature": 0.5,
            "max_tokens": 2048,
            "timeout": 30
        },
        "stages": {
            "genesis": 2048,
            "narrator": 1024,
            "map_gen": 512,
            "cognition": 512
        },
        "minio": {
            "endpoint": "localhost:9000",
            "access_key": "test-access",
            "secret_key": "test-secret",
            "secure": False,
            "bucket_name": "test-bucket"
        },
        "redis": {
            "host": "localhost",
            "port": 6379,
            "password": None,
            "db": 0,
            "ttl": 3600
        }
    }
    settings.AGENT_CONFIG = test_config

    yield test_config

    # Restore original config
    settings.AGENT_CONFIG = original_config


# ============================================================================
# Markers
# ============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "robustness: Robustness and error handling tests")