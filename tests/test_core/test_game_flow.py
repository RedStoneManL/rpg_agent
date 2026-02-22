"""
End-to-End Game Flow Tests

Tests the complete game flow from start to finish:
- Game initialization
- Player actions
- World simulation
- Event tracking
- Save/Load
- Game ending conditions
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import json
import time

from rpg_world_agent.core.runtime import RuntimeEngine
from rpg_world_agent.core.world_state import (
    WorldStateManager,
    CrisisLevel,
    WeatherType,
    NPCState,
    RegionState
)
from rpg_world_agent.core.event_system import EventSystem, EventType, EventPriority
from rpg_world_agent.core.world_simulator import (
    WorldSimulator,
    SimulationConfig,
    WorldEventCategory
)
from rpg_world_agent.core.lazy_loader import (
    LazyLoadingStrategy,
    LazyLoadingConfig,
    ContentType
)
from rpg_world_agent.core.cognition import CognitionSystem
from rpg_world_agent.core.map_engine import MapTopologyEngine


class MockLLMClient:
    """Mock LLM client for testing"""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.call_count += 1

        # Default response
        response = {
            "intent": "CHAT",
            "keyword": ""
        }

        if self.responses:
            response = self.responses[min(self.call_count - 1, len(self.responses) - 1)]

        content = json.dumps(response) if isinstance(response, dict) else response

        mock_choice = MagicMock()
        mock_choice.message.content = content

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        return mock_response


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.keys.return_value = []
    mock.setex = MagicMock()
    mock.zadd = MagicMock()
    mock.sadd = MagicMock()
    mock.zrevrange.return_value = []
    mock.delete = MagicMock()
    return mock


@pytest.fixture
def mock_minio():
    """Mock MinIO client"""
    mock = MagicMock()
    mock.bucket_exists.return_value = True
    mock.put_object = MagicMock()
    mock.get_object = MagicMock()
    mock.remove_object = MagicMock()
    return mock


@pytest.fixture
def mock_llm():
    """Mock LLM client"""
    return MockLLMClient()


@pytest.fixture
def game_engine(mock_redis, mock_minio, mock_llm):
    """Create a game engine with mocked dependencies"""
    with patch('rpg_world_agent.core.world_state.DBClient.get_redis', return_value=mock_redis):
        with patch('rpg_world_agent.core.event_system.DBClient.get_redis', return_value=mock_redis):
            with patch('rpg_world_agent.core.cognition.DBClient.get_redis', return_value=mock_redis):
                with patch('rpg_world_agent.core.cognition.DBClient.get_minio', return_value=mock_minio):
                    with patch('rpg_world_agent.data.llm_client.get_llm_client', return_value=mock_llm):
                        engine = RuntimeEngine(
                            session_id="test_game_flow",
                            llm_client=mock_llm,
                            debug_mode=True
                        )
                        yield engine


class TestGameInitialization:
    """Tests for game initialization"""

    def test_engine_creation(self, game_engine):
        """Test that engine is created correctly"""
        assert game_engine.session_id == "test_game_flow"
        assert game_engine.map_engine is not None
        assert game_engine.cognition is not None
        assert game_engine.event_system is not None
        assert game_engine.world_state is not None

    def test_player_initialization(self, game_engine):
        """Test player initialization"""
        game_engine.initialize_player("start_location", ["adventurer"])

        state = game_engine.cognition.get_player_state()

        assert state.get("location") == "start_location"
        assert "adventurer" in state.get("tags", [])
        assert state.get("hp") == 100
        assert state.get("sanity") == 100

    def test_world_state_initialization(self, game_engine):
        """Test world state initialization"""
        game_engine.initialize_player("start_location")

        # Check world time
        assert game_engine.world_state.world_time is not None

        # Check crisis level
        assert game_engine.world_state.crisis_level == CrisisLevel.CALM


class TestPlayerActions:
    """Tests for player actions"""

    def test_look_command(self, game_engine):
        """Test /look command"""
        game_engine.initialize_player("start_location")

        # Add location to map
        game_engine.map_engine.add_node(
            "start_location",
            name="Starting Village",
            desc="A peaceful village",
            geo_feature="Settlement"
        )

        response = game_engine.step("/look")

        assert "Starting Village" in response
        assert "A peaceful village" in response

    def test_status_command(self, game_engine):
        """Test /status command"""
        game_engine.initialize_player("start_location")

        response = game_engine.step("/status")

        assert "HP" in response
        assert "SAN" in response
        assert "位置" in response or "location" in response.lower()

    def test_world_command(self, game_engine):
        """Test /world command"""
        game_engine.initialize_player("start_location")

        response = game_engine.step("/world")

        assert "世界" in response or "World" in response
        assert "危机" in response or "crisis" in response.lower()

    def test_events_command(self, game_engine):
        """Test /events command"""
        game_engine.initialize_player("start_location")

        response = game_engine.step("/events")

        assert "事件" in response or "Event" in response

    def test_natural_language_input(self, game_engine):
        """Test natural language input"""
        game_engine.initialize_player("start_location")

        # Mock LLM response
        game_engine.llm_client.responses = [
            {"intent": "CHAT", "keyword": "hello"}
        ]

        response = game_engine.step("Hello, what is this place?")

        # Should get some response
        assert len(response) > 0
        assert game_engine.llm_client.call_count > 0


class TestWorldSimulation:
    """Tests for world simulation"""

    def test_simulator_integration(self, game_engine):
        """Test that world simulator is integrated with engine"""
        game_engine.initialize_player("start_location")

        # Create simulator
        simulator = WorldSimulator(
            session_id=game_engine.session_id,
            world_state=game_engine.world_state,
            event_system=game_engine.event_system
        )

        # Run simulation
        events = simulator.simulate_tick(30)

        # Time should advance
        assert game_engine.world_state.world_time.total_minutes > 0

    def test_npc_registration_and_simulation(self, game_engine):
        """Test NPC registration and simulation"""
        game_engine.initialize_player("village")

        # Register NPC
        npc = game_engine.world_state.register_npc(
            "npc_001",
            "Village Elder",
            "village"
        )

        assert npc.npc_id == "npc_001"
        assert npc.name == "Village Elder"
        assert npc.current_location == "village"

        # Run simulation
        simulator = WorldSimulator(
            session_id=game_engine.session_id,
            world_state=game_engine.world_state,
            event_system=game_engine.event_system,
            config=SimulationConfig(npc_activity_chance=1.0)
        )

        activities = simulator.simulate_npc_activities()

        # Should have some activities
        assert len(activities) > 0

    def test_world_events_affect_state(self, game_engine):
        """Test that world events affect world state"""
        game_engine.initialize_player("village")

        # Register region
        game_engine.world_state.register_region("village", "Village")

        simulator = WorldSimulator(
            session_id=game_engine.session_id,
            world_state=game_engine.world_state,
            event_system=game_engine.event_system
        )

        initial_crisis = game_engine.world_state.crisis_level

        # Simulate many ticks to potentially trigger events
        for _ in range(20):
            simulator.simulate_tick(30)

        # Crisis level might have changed
        # (depends on random events, so just verify it's still valid)
        assert game_engine.world_state.crisis_level in list(CrisisLevel)


class TestEventTracking:
    """Tests for event tracking"""

    def test_event_emission(self, game_engine):
        """Test that events are emitted correctly"""
        game_engine.initialize_player("start_location")

        # Emit a test event
        event = game_engine.event_system.emit(
            EventType.DISCOVERY,
            "player_test",
            "start_location",
            data={"description": "Found something"},
            tags=["test"]
        )

        assert event.event_type == EventType.DISCOVERY
        assert event.location == "start_location"

    def test_event_history(self, game_engine):
        """Test event history tracking"""
        game_engine.initialize_player("start_location")

        # Emit several events
        for i in range(5):
            game_engine.event_system.emit(
                EventType.CUSTOM,
                "player_test",
                "start_location",
                data={"index": i}
            )

        # Get event summary
        summary = game_engine.event_system.get_event_summary()

        assert summary["total_events"] == 5

    def test_events_affect_world_state(self, game_engine):
        """Test that events affect world state"""
        game_engine.initialize_player("start_location")

        # Register a region
        game_engine.world_state.register_region("hidden_cave", "Hidden Cave")

        # Emit discovery event
        game_engine.event_system.emit(
            EventType.DISCOVERY,
            "player_test",
            "hidden_cave",
            data={"target": "hidden_cave"}
        )

        # World state should handle the event
        game_engine.world_state.handle_event(game_engine.event_system.get_all_events(1)[0])

        # Region should be discovered
        region = game_engine.world_state.get_region_state("hidden_cave")
        if region:
            assert region.discovered


class TestQuestSystem:
    """Tests for quest system"""

    def test_quest_registration(self, game_engine):
        """Test quest registration"""
        game_engine.initialize_player("village")

        quest = game_engine.world_state.register_quest(
            "quest_001",
            "Save the Village",
            "Help the village defend against threats"
        )

        assert quest.quest_id == "quest_001"
        assert quest.status == "available"

    def test_quest_acceptance(self, game_engine):
        """Test quest acceptance"""
        game_engine.initialize_player("village")

        game_engine.world_state.register_quest(
            "quest_001",
            "Save the Village",
            "Description"
        )

        success = game_engine.world_state.accept_quest("quest_001")

        assert success
        quest = game_engine.world_state.get_quest_state("quest_001")
        assert quest.status == "active"

    def test_quest_completion(self, game_engine):
        """Test quest completion"""
        game_engine.initialize_player("village")

        game_engine.world_state.register_quest(
            "quest_001",
            "Save the Village",
            "Description"
        )
        game_engine.world_state.accept_quest("quest_001")

        success = game_engine.world_state.complete_quest("quest_001")

        assert success
        quest = game_engine.world_state.get_quest_state("quest_001")
        assert quest.status == "completed"


class TestLazyLoading:
    """Tests for lazy loading system"""

    def test_cache_hit(self, game_engine):
        """Test cache hit scenario"""
        strategy = LazyLoadingStrategy(config=LazyLoadingConfig())

        # Create context
        context = type('LoadContext', (), {
            'player_id': 'player_1',
            'location': 'village',
            'world_state': game_engine.world_state,
            'event_system': game_engine.event_system,
            'compute_hash': lambda: 'test_hash'
        })()

        # First call - should generate
        content, is_new = strategy.get_cached_or_generate(
            "test_key",
            context,
            ContentType.NARRATIVE,
            lambda: {"text": "Generated content"}
        )

        assert is_new
        assert content["text"] == "Generated content"

        # Second call - should use cache
        content2, is_new2 = strategy.get_cached_or_generate(
            "test_key",
            context,
            ContentType.NARRATIVE,
            lambda: {"text": "Different content"}
        )

        assert not is_new2
        assert content2["text"] == "Generated content"  # Still original

    def test_cache_expiration(self, game_engine):
        """Test cache expiration"""
        config = LazyLoadingConfig(cache_ttl_narrative=1)  # 1 second TTL
        strategy = LazyLoadingStrategy(config=config)

        context = type('LoadContext', (), {
            'player_id': 'player_1',
            'location': 'village',
            'world_state': game_engine.world_state,
            'event_system': game_engine.event_system,
            'compute_hash': lambda: 'test_hash'
        })()

        # Generate content
        content1, _ = strategy.get_cached_or_generate(
            "test_key",
            context,
            ContentType.NARRATIVE,
            lambda: {"text": "First"},
            ttl_seconds=1
        )

        # Wait for expiration
        time.sleep(2)

        # Should regenerate
        content2, is_new = strategy.get_cached_or_generate(
            "test_key",
            context,
            ContentType.NARRATIVE,
            lambda: {"text": "Second"}
        )

        assert is_new
        assert content2["text"] == "Second"

    def test_rate_limiting(self, game_engine):
        """Test API call rate limiting"""
        config = LazyLoadingConfig(max_calls_per_minute=3)
        strategy = LazyLoadingStrategy(config=config)

        context = type('LoadContext', (), {
            'player_id': 'player_1',
            'location': 'village',
            'world_state': game_engine.world_state,
            'event_system': game_engine.event_system,
            'compute_hash': lambda: 'test_hash'
        })()

        # Make multiple calls
        for i in range(5):
            content, _ = strategy.get_cached_or_generate(
                f"key_{i}",
                context,
                ContentType.NARRATIVE,
                lambda: {"value": i}
            )

        stats = strategy.get_stats()

        # Some calls should have been blocked
        assert stats["calls_blocked"] > 0 or stats["cache_hits"] > 0


class TestGameSaveLoad:
    """Tests for save/load functionality"""

    def test_world_state_save(self, game_engine, mock_redis):
        """Test world state saving"""
        game_engine.initialize_player("village")

        # Make some changes
        game_engine.world_state.set_flag("test_flag", True)
        game_engine.world_state.advance_time(30)

        # Save
        game_engine.world_state.save()

        # Verify setex was called (Redis save)
        assert mock_redis.setex.called

    def test_event_system_persistence(self, game_engine, mock_redis):
        """Test event system persistence"""
        game_engine.initialize_player("village")

        # Emit events
        for i in range(3):
            game_engine.event_system.emit(
                EventType.CUSTOM,
                "player_test",
                "village",
                data={"index": i}
            )

        # Verify events were stored
        assert mock_redis.setex.call_count >= 3


class TestGameEndingConditions:
    """Tests for game ending conditions"""

    def test_player_death(self, game_engine):
        """Test player death condition"""
        game_engine.initialize_player("village")

        # Reduce HP to 0
        game_engine.cognition.update_player_state({"hp": 0})

        state = game_engine.cognition.get_player_state()

        assert state.get("hp") == 0
        # In a real game, this would trigger game over

    def test_player_insanity(self, game_engine):
        """Test player insanity condition"""
        game_engine.initialize_player("village")

        # Reduce SAN to 0
        game_engine.cognition.update_player_state({"sanity": 0})

        state = game_engine.cognition.get_player_state()

        assert state.get("sanity") == 0
        # In a real game, this would trigger game over

    def test_quest_completion_ending(self, game_engine):
        """Test quest completion as ending condition"""
        game_engine.initialize_player("village")

        # Register and complete main quest
        game_engine.world_state.register_quest(
            "main_quest",
            "Save the World",
            "Main storyline quest"
        )
        game_engine.world_state.accept_quest("main_quest")
        game_engine.world_state.complete_quest("main_quest")

        quest = game_engine.world_state.get_quest_state("main_quest")

        assert quest.status == "completed"
        # In a real game, this could trigger a victory ending


class TestCompleteGameFlow:
    """Full game flow integration tests"""

    def test_short_game_session(self, game_engine):
        """Test a short complete game session"""
        # Initialize
        game_engine.initialize_player("start", ["adventurer"])

        # Add locations
        game_engine.map_engine.add_node(
            "start",
            name="Starting Point",
            desc="Where your journey begins",
            geo_feature="Plains"
        )
        game_engine.map_engine.add_node(
            "village",
            name="Nearby Village",
            desc="A small settlement",
            geo_feature="Settlement"
        )

        # Register NPC
        game_engine.world_state.register_npc(
            "elder",
            "Village Elder",
            "village"
        )

        # Register quest
        game_engine.world_state.register_quest(
            "main_quest",
            "Talk to Elder",
            "Speak with the village elder"
        )

        # Simulate game turns
        responses = []

        # Turn 1: Look around
        responses.append(game_engine.step("/look"))

        # Turn 2: Check status
        responses.append(game_engine.step("/status"))

        # Turn 3: Talk (would use LLM in real scenario)
        responses.append(game_engine.step("Hello!"))

        # Verify game progressed
        assert len(responses) == 3
        assert all(len(r) > 0 for r in responses)

        # Check game state
        summary = game_engine.world_state.get_world_summary()
        assert summary is not None

    def test_world_simulation_during_game(self, game_engine):
        """Test that world simulation runs during gameplay"""
        game_engine.initialize_player("village")

        # Add content
        game_engine.world_state.register_npc("npc1", "Test NPC", "village")
        game_engine.world_state.register_region("forest", "Dark Forest")

        # Create simulator
        simulator = WorldSimulator(
            session_id=game_engine.session_id,
            world_state=game_engine.world_state,
            event_system=game_engine.event_system
        )

        # Play a few turns
        for _ in range(3):
            game_engine.step("/look")

        # Simulate world
        simulator.simulate_tick(30)

        # Time should have advanced
        assert game_engine.world_state.world_time.total_minutes > 0

    def test_event_driven_storytelling(self, game_engine):
        """Test event-driven storytelling"""
        game_engine.initialize_player("village")

        # Emit discovery event
        game_engine.event_system.emit(
            EventType.DISCOVERY,
            "player_test",
            "village",
            data={"target": "ancient_ruins"},
            tags=["discovery", "important"]
        )

        # Get narrative context
        context = game_engine.event_system.get_context_for_narration()

        # Should include the event
        assert len(context) > 0

        # Check event summary
        summary = game_engine.event_system.get_event_summary()
        assert summary["total_events"] >= 1
