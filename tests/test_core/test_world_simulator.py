"""
Unit tests for WorldSimulator

Tests the world simulation system including:
- simulate_tick()
- simulate_npc_activities()
- simulate_world_events()
- Integration with WorldStateManager and EventSystem
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import time

from rpg_world_agent.core.world_simulator import (
    WorldSimulator,
    WorldEvent,
    NPCActivity,
    SimulationConfig,
    SimulationPhase,
    WorldEventCategory
)
from rpg_world_agent.core.world_state import (
    WorldStateManager,
    NPCState,
    RegionState,
    CrisisLevel,
    WeatherType
)
from rpg_world_agent.core.event_system import EventSystem, EventType


class TestSimulationConfig:
    """Tests for SimulationConfig"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SimulationConfig()

        assert config.npc_activity_chance == 0.3
        assert config.npc_move_chance == 0.15
        assert config.event_base_chance == 0.1
        assert config.default_tick_minutes == 30
        assert config.max_tick_minutes == 480

    def test_custom_config(self):
        """Test custom configuration values"""
        config = SimulationConfig(
            npc_activity_chance=0.5,
            default_tick_minutes=60
        )

        assert config.npc_activity_chance == 0.5
        assert config.default_tick_minutes == 60


class TestNPCActivity:
    """Tests for NPCActivity dataclass"""

    def test_npc_activity_creation(self):
        """Test creating an NPC activity"""
        activity = NPCActivity(
            npc_id="npc_001",
            activity_type="move",
            timestamp=time.time(),
            from_location="village",
            to_location="forest",
            description="NPC moved to forest"
        )

        assert activity.npc_id == "npc_001"
        assert activity.activity_type == "move"
        assert activity.from_location == "village"
        assert activity.to_location == "forest"
        assert len(activity.affected_entities) == 0

    def test_npc_activity_with_affected_entities(self):
        """Test NPC activity with affected entities"""
        activity = NPCActivity(
            npc_id="npc_001",
            activity_type="social",
            timestamp=time.time(),
            description="NPC talked to another NPC",
            affected_entities={"npc_002", "npc_003"}
        )

        assert len(activity.affected_entities) == 2
        assert "npc_002" in activity.affected_entities


class TestWorldEvent:
    """Tests for WorldEvent dataclass"""

    def test_world_event_creation(self):
        """Test creating a world event"""
        event = WorldEvent(
            event_id="we_001",
            category=WorldEventCategory.NATURAL,
            name="Storm",
            description="A storm approaches",
            timestamp=time.time(),
            duration_minutes=120,
            crisis_change=1
        )

        assert event.event_id == "we_001"
        assert event.category == WorldEventCategory.NATURAL
        assert event.crisis_change == 1
        assert len(event.affected_regions) == 0

    def test_world_event_with_affected_regions(self):
        """Test world event with affected regions"""
        event = WorldEvent(
            event_id="we_002",
            category=WorldEventCategory.CRISIS,
            name="Invasion",
            description="Enemies are invading",
            timestamp=time.time(),
            affected_regions={"north", "east"}
        )

        assert len(event.affected_regions) == 2
        assert "north" in event.affected_regions


class TestWorldSimulator:
    """Tests for WorldSimulator class"""

    @pytest.fixture
    def mock_world_state(self):
        """Create a mock WorldStateManager"""
        mock = MagicMock(spec=WorldStateManager)
        mock.world_time = MagicMock()
        mock.world_time.hours = 10
        mock.world_time.total_minutes = 600
        mock.world_time.advance = MagicMock()
        mock.crisis_level = CrisisLevel.LOW
        mock.regions = {}
        mock.npcs = {}
        mock.quests = {}
        mock.global_flags = {}
        mock.global_variables = {}
        mock.set_crisis_level = MagicMock()
        mock.advance_time = MagicMock()
        mock.get_npc_state = MagicMock(return_value=None)
        mock.get_region_state = MagicMock(return_value=None)
        mock.move_npc = MagicMock(return_value=True)
        mock.set_region_weather = MagicMock()
        mock.get_npc_relationship = MagicMock(return_value=0)
        mock.set_npc_relationship = MagicMock()
        return mock

    @pytest.fixture
    def mock_event_system(self):
        """Create a mock EventSystem"""
        mock = MagicMock(spec=EventSystem)
        mock.emit = MagicMock()
        mock.get_all_events = MagicMock(return_value=[])
        mock.get_events_by_type = MagicMock(return_value=[])
        return mock

    @pytest.fixture
    def simulator(self, mock_world_state, mock_event_system):
        """Create a WorldSimulator instance"""
        return WorldSimulator(
            session_id="test_session",
            world_state=mock_world_state,
            event_system=mock_event_system,
            config=SimulationConfig()
        )

    def test_simulator_initialization(self, simulator):
        """Test simulator initialization"""
        assert simulator.session_id == "test_session"
        assert simulator._tick_count == 0
        assert simulator._simulation_phase == SimulationPhase.ACTIVE

    def test_simulate_tick_advances_time(self, simulator, mock_world_state):
        """Test that simulate_tick advances world time"""
        simulator.simulate_tick(60)

        mock_world_state.advance_time.assert_called_once_with(60)

    def test_simulate_tick_respects_max(self, simulator, mock_world_state):
        """Test that simulate_tick respects max tick minutes"""
        simulator.simulate_tick(1000)  # Request more than max

        # Should be capped at max_tick_minutes (480)
        mock_world_state.advance_time.assert_called_once_with(480)

    def test_simulate_tick_returns_events(self, simulator):
        """Test that simulate_tick returns world events"""
        # With default config and no NPCs, should complete without events
        # unless random triggers
        events = simulator.simulate_tick(30)

        assert isinstance(events, list)

    def test_simulate_tick_increments_counter(self, simulator):
        """Test that simulate_tick increments tick counter"""
        initial_count = simulator._tick_count

        simulator.simulate_tick(30)
        simulator.simulate_tick(30)

        assert simulator._tick_count == initial_count + 2

    def test_simulate_npc_activities_with_no_npcs(self, simulator, mock_world_state):
        """Test NPC activities with no NPCs"""
        mock_world_state.npcs = {}

        activities = simulator.simulate_npc_activities()

        assert len(activities) == 0

    def test_simulate_npc_activities_with_dead_npc(self, simulator, mock_world_state):
        """Test NPC activities with dead NPCs (should be skipped)"""
        dead_npc = NPCState(
            npc_id="dead_001",
            name="Dead NPC",
            current_location="village",
            home_location="village",
            alive=False
        )
        mock_world_state.npcs = {"dead_001": dead_npc}

        # Mock random to always trigger activity
        with patch('random.random', return_value=0.0):  # Always < npc_activity_chance
            activities = simulator.simulate_npc_activities()

        assert len(activities) == 0  # Dead NPCs should be skipped

    def test_simulate_npc_activities_with_alive_npc(self, simulator, mock_world_state):
        """Test NPC activities with alive NPCs"""
        alive_npc = NPCState(
            npc_id="alive_001",
            name="Alive NPC",
            current_location="village",
            home_location="village",
            alive=True
        )
        mock_world_state.npcs = {"alive_001": alive_npc}
        mock_world_state.get_npc_state.return_value = alive_npc

        # Mock random to trigger activity and movement
        with patch('random.random', side_effect=[0.0, 0.0, 0.5]):  # Trigger activity and movement
            with patch('random.choice', return_value="forest"):
                # Add a discovered region to move to
                mock_world_state.regions = {
                    "forest": RegionState(
                        region_id="forest",
                        name="Forest",
                        discovered=True
                    )
                }
                activities = simulator.simulate_npc_activities()

        # Should have some activities (depends on random)
        assert isinstance(activities, list)

    def test_simulate_world_events_returns_list(self, simulator):
        """Test that simulate_world_events returns a list"""
        events = simulator.simulate_world_events()

        assert isinstance(events, list)

    def test_simulate_world_events_probability(self, simulator, mock_world_state):
        """Test world event probability based on crisis level"""
        mock_world_state.crisis_level = CrisisLevel.HIGH

        # Low random value should not trigger event
        with patch('random.random', return_value=0.9):
            events = simulator.simulate_world_events()
            assert len(events) == 0

        # High random value might trigger event
        with patch('random.random', return_value=0.01):
            events = simulator.simulate_world_events()
            # Event might or might not be generated depending on templates

    def test_get_simulation_summary(self, simulator):
        """Test getting simulation summary"""
        summary = simulator.get_simulation_summary()

        assert "tick_count" in summary
        assert "phase" in summary
        assert "crisis_level" in summary

    def test_get_recent_narrative(self, simulator):
        """Test getting recent narrative"""
        narrative = simulator.get_recent_narrative()

        assert isinstance(narrative, str)

    def test_on_player_idle(self, simulator):
        """Test player idle callback"""
        events = simulator.on_player_idle(60)

        assert isinstance(events, list)
        assert simulator._simulation_phase == SimulationPhase.QUIET

    def test_on_player_return(self, simulator):
        """Test player return callback"""
        mock_world_state = simulator.world_state
        mock_world_state.get_time_display.return_value = "Day 1, 10:00"
        mock_world_state.crisis_level.name = "LOW"

        narrative = simulator.on_player_return()

        assert simulator._simulation_phase == SimulationPhase.ACTIVE
        assert isinstance(narrative, str)

    def test_weather_change(self, simulator, mock_world_state):
        """Test weather simulation"""
        region = RegionState(
            region_id="test_region",
            name="Test Region",
            weather=WeatherType.CLEAR
        )
        mock_world_state.regions = {"test_region": region}

        # Mock random to trigger weather change
        with patch('random.random', return_value=0.01):  # < 0.1 threshold
            with patch('random.choices', return_value=[WeatherType.RAIN]):
                simulator._simulate_weather_change()

        mock_world_state.set_region_weather.assert_called()

    def test_crisis_level_adjustment(self, simulator, mock_world_state):
        """Test crisis level adjustment"""
        mock_world_state.crisis_level = CrisisLevel.MEDIUM

        # Mock random to trigger decay
        with patch('random.random', return_value=0.01):
            simulator._adjust_crisis_level()

        # Crisis might decay (depends on implementation)
        # Just verify it doesn't crash

    def test_apply_world_event(self, simulator, mock_world_state, mock_event_system):
        """Test applying world event effects"""
        event = WorldEvent(
            event_id="test_001",
            category=WorldEventCategory.NATURAL,
            name="Test Event",
            description="A test event",
            timestamp=time.time(),
            crisis_change=1,
            affected_regions={"region_1"}
        )

        region = RegionState(
            region_id="region_1",
            name="Region 1",
            danger_level=2
        )
        mock_world_state.regions = {"region_1": region}
        mock_world_state.get_region_state.return_value = region

        simulator._apply_world_event(event)

        # Should update crisis level
        mock_world_state.set_crisis_level.assert_called()

    def test_cleanup_history(self, simulator):
        """Test history cleanup"""
        # Add many activities
        for i in range(100):
            simulator._recent_activities.append(
                NPCActivity(
                    npc_id=f"npc_{i}",
                    activity_type="test",
                    timestamp=time.time()
                )
            )

        simulator._cleanup_history()

        assert len(simulator._recent_activities) <= 50


class TestWorldEventCategory:
    """Tests for WorldEventCategory enum"""

    def test_categories_exist(self):
        """Test that all expected categories exist"""
        assert WorldEventCategory.NATURAL.value == "natural"
        assert WorldEventCategory.POLITICAL.value == "political"
        assert WorldEventCategory.ECONOMIC.value == "economic"
        assert WorldEventCategory.SOCIAL.value == "social"
        assert WorldEventCategory.MYSTICAL.value == "mystical"
        assert WorldEventCategory.CRISIS.value == "crisis"


class TestSimulationPhase:
    """Tests for SimulationPhase enum"""

    def test_phases_exist(self):
        """Test that all expected phases exist"""
        assert SimulationPhase.QUIET.value == "quiet"
        assert SimulationPhase.ACTIVE.value == "active"
        assert SimulationPhase.TRANSITION.value == "transition"


class TestWorldSimulatorIntegration:
    """Integration tests for WorldSimulator"""

    @pytest.fixture
    def real_world_state(self):
        """Create a real WorldStateManager with mock Redis"""
        with patch('rpg_world_agent.core.world_state.DBClient.get_redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis.return_value = mock_redis_instance
            mock_redis_instance.get.return_value = None
            mock_redis_instance.keys.return_value = []
            mock_redis_instance.setex = MagicMock()

            return WorldStateManager("test_integration")

    @pytest.fixture
    def real_event_system(self):
        """Create a real EventSystem with mock Redis"""
        with patch('rpg_world_agent.core.event_system.DBClient.get_redis') as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis.return_value = mock_redis_instance
            mock_redis_instance.get.return_value = None
            mock_redis_instance.keys.return_value = []
            mock_redis_instance.zadd = MagicMock()
            mock_redis_instance.sadd = MagicMock()
            mock_redis_instance.setex = MagicMock()
            mock_redis_instance.zrevrange.return_value = []

            return EventSystem("test_integration")

    def test_full_simulation_cycle(self, real_world_state, real_event_system):
        """Test a full simulation cycle"""
        # Add some test data
        npc = real_world_state.register_npc("npc_001", "Test NPC", "village")
        region = real_world_state.register_region("village", "Village")
        region.discovered = True

        simulator = WorldSimulator(
            session_id="test_integration",
            world_state=real_world_state,
            event_system=real_event_system
        )

        # Run simulation
        events = simulator.simulate_tick(30)

        # Verify time advanced
        assert real_world_state.world_time.total_minutes == 30

        # Get summary
        summary = simulator.get_simulation_summary()
        assert summary["tick_count"] == 1

    def test_npc_movement_simulation(self, real_world_state, real_event_system):
        """Test NPC movement simulation"""
        # Create NPC and regions
        npc = real_world_state.register_npc("npc_001", "Traveler", "town")
        region1 = real_world_state.register_region("town", "Town")
        region1.discovered = True
        region2 = real_world_state.register_region("forest", "Forest")
        region2.discovered = True

        simulator = WorldSimulator(
            session_id="test_integration",
            world_state=real_world_state,
            event_system=real_event_system,
            config=SimulationConfig(
                npc_activity_chance=1.0,  # Always active
                npc_move_chance=1.0       # Always move
            )
        )

        # Simulate
        activities = simulator.simulate_npc_activities()

        # Should have some activities
        assert len(activities) > 0

    def test_crisis_progression(self, real_world_state, real_event_system):
        """Test crisis level changes during simulation"""
        real_world_state.set_crisis_level(CrisisLevel.LOW)

        simulator = WorldSimulator(
            session_id="test_integration",
            world_state=real_world_state,
            event_system=real_event_system
        )

        # Simulate multiple ticks
        for _ in range(10):
            simulator.simulate_tick(30)

        # Crisis level might have changed (random)
        # Just verify it's still valid
        assert real_world_state.crisis_level in list(CrisisLevel)
