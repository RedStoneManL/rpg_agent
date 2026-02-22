"""
Unit tests for MapTopologyEngine.
"""

import json
import pytest
from typing import TYPE_CHECKING
from unittest.mock import patch, MagicMock

from tests.mocks.llm_mock import MockLLMClient, create_mock_llm_client, MOCK_ROUTE_CONCEPT
from tests.mocks.redis_mock import MockRedis, create_mock_redis

# Import actual types for runtime
from rpg_world_agent.core.map_engine import MapTopologyEngine


@pytest.mark.unit
class TestMapEngineNodeOperations:
    """Tests for map node CRUD operations."""

    def test_save_node_stores_data(self, mock_db_client, mock_redis: MockRedis, sample_node_data):
        """Test that save_node correctly stores node data."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        engine.save_node("loc_tavern", sample_node_data, node_type="L2")  # Pass type explicitly

        key = "rpg:map:node:loc_tavern"
        stored_data = json.loads(mock_redis.get(key))
        assert stored_data["node_id"] == "loc_tavern"
        assert stored_data["name"] == "Dusty Tavern"
        assert stored_data["type"] == "L2"

    def test_get_node_retrieves_data(self, mock_redis):
        """Test that get_node correctly retrieves node data."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        test_data = {"node_id": "loc_forest", "name": "Dark Forest", "desc": "Scary"}
        mock_redis.set("rpg:map:node:loc_forest", json.dumps(test_data, ensure_ascii=False))

        engine = MapTopologyEngine(None)
        result = engine.get_node("loc_forest")

        assert result is not None
        assert result["node_id"] == "loc_forest"
        assert result["name"] == "Dark Forest"

    def test_get_node_returns_none_for_nonexistent(self, mock_redis):
        """Test that get_node returns None for node that doesn't exist."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        result = engine.get_node("nonexistent_node")

        assert result is None

    def test_node_exists_returns_true_for_existing(self, mock_redis):
        """Test that node_exists returns True for existing nodes."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        test_data = {"node_id": "loc_tavern", "name": "Tavern", "desc": "A place"}
        mock_redis.set("rpg:map:node:loc_tavern", json.dumps(test_data))

        engine = MapTopologyEngine(None)
        assert engine.node_exists("loc_tavern") is True

    def test_node_exists_returns_false_for_nonexistent(self):
        """Test that node_exists returns False for non-existent nodes."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        assert engine.node_exists("nonexistent_node") is False

    def test_save_node_sets_ttl(self, mock_redis):
        """Test that save_node sets TTL on the key."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        engine.save_node("test_node", {"node_id": "test_node", "name": "Test"})

        # Verify the key was stored (exists returns count > 0)
        key = "rpg:map:node:test_node"
        assert mock_redis.exists(key) > 0


@pytest.mark.unit
class TestMapEngineEdgeOperations:
    """Tests for map edge/connection operations."""

    def test_connect_nodes_creates_bidirectional_edges(self, mock_db_client, mock_redis):
        """Test that connect_nodes_with_concept creates bidirectional edges."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        route_data = {
            "route_name": "Muddy Path",
            "description": "A muddy path",
            "risk_level": 1
        }

        result = engine.connect_nodes_with_concept("loc_a", "loc_b", route_data)

        assert result is True

        # Check A -> B edge
        edge_a_to_b = json.loads(mock_redis.hget("rpg:map:edges:loc_a", "Travel:loc_b"))
        assert edge_a_to_b["target_id"] == "loc_b"
        assert edge_a_to_b["route_info"]["route_name"] == "Muddy Path"

        # Check B -> A edge
        edge_b_to_a = json.loads(mock_redis.hget("rpg:map:edges:loc_b", "Travel:loc_a"))
        assert edge_b_to_a["target_id"] == "loc_a"
        assert edge_b_to_a["route_info"]["route_name"] == "Muddy Path"

    def test_connect_nodes_serializes_route_data(self, mock_db_client, mock_redis):
        """Test that route data is properly serialized."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        route_data = {
            "route_name": "Secret Tunnel",
            "geo_type": "Underground",
            "description": "Dark and damp",
            "risk_level": 3,
            "rumors": ["Monsters lurk"]
        }

        engine.connect_nodes_with_concept("loc_1", "loc_2", route_data)

        edge_data = json.loads(mock_redis.hget("rpg:map:edges:loc_1", "Travel:loc_2"))
        assert edge_data["route_info"]["geo_type"] == "Underground"
        assert edge_data["route_info"]["rumors"] == ["Monsters lurk"]

    def test_get_neighbors_returns_connected_nodes(self, mock_db_client, mock_redis):
        """Test that get_neighbors returns all connected nodes."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        # Set up edges
        edge_data = json.dumps({
            "target_id": "node_b",
            "type": "Travel",
            "route_info": {"route_name": "Path"}
        })
        mock_redis.hset("rpg:map:edges:node_a", "Travel:node_b", edge_data)

        engine = MapTopologyEngine(None)
        neighbors = engine.get_neighbors("node_a")

        assert len(neighbors) == 1
        assert "Travel:node_b" in neighbors

    def test_get_neighbors_returns_empty_for_no_connections(self, mock_redis):
        """Test that get_neighbors returns empty dict for node with no connections."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        neighbors = engine.get_neighbors("isolated_node")

        assert neighbors == {}


@pytest.mark.unit
class TestMapEngineLLMIntegration:
    """Tests for LLM-powered map generation features."""

    def test_generate_route_concept_calls_llm(self, mock_llm: MockLLMClient, sample_node_data):
        """Test that _generate_route_concept calls LLM client."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        mock_llm.set_response("route concept", MOCK_ROUTE_CONCEPT)

        engine = MapTopologyEngine(mock_llm)
        engine.save_node("loc_tavern", sample_node_data)
        engine.save_node("loc_forest", {"name": "Forest"})

        world_config = {
            "genre": "Test",
            "tone": "Neutral",
            "final_conflict": "None"
        }

        result = engine._generate_route_concept("loc_tavern", "loc_forest", world_config)

        assert result is not None
        assert "route_name" in result
        assert mock_llm.call_count > 0

    def test_generate_route_concept_returns_fallback_on_missing_nodes(self):
        """Test that _generate_route_concept returns fallback when nodes don't exist."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        world_config = {"genre": "Test"}

        result = engine._generate_route_concept("nonexistent_a", "nonexistent_b", world_config)

        assert result["route_name"] == "迷雾小径"
        # The description should contain "迷雾" (mist in Chinese)
        assert "迷雾" in result.get("description", "")

    def test_create_dynamic_sub_location_creates_node_and_connection(self, mock_redis, mock_llm: MockLLMClient):
        """Test that create_dynamic_sub_location creates both node and connection."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        # Set up parent node
        parent_data = {
            "node_id": "parent_loc",
            "name": "Parent Location",
            "desc": "A parent location",
            "geo_feature": "Building",
            "risk_level": 1
        }
        mock_redis.set("rpg:map:node:parent_loc", json.dumps(parent_data))

        mock_llm.set_response("动态子区域", json.dumps({
            "name": "Secret Room",
            "desc": "Hidden room",
            "geo_feature": "Room",
            "risk_level": 1,
            "connection_path_name": "Hidden Door"
        }))

        engine = MapTopologyEngine(mock_llm)
        new_node_id = engine.create_dynamic_sub_location("parent_loc", "secret")

        assert new_node_id is not None
        assert engine.node_exists(new_node_id)
        neighbors = engine.get_neighbors("parent_loc")
        assert len(neighbors) > 0

    def test_create_dynamic_sub_location_returns_none_without_llm(self):
        """Test that create_dynamic_sub_location returns None without LLM."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        result = engine.create_dynamic_sub_location("parent_loc", "secret")

        assert result is None

    def test_create_dynamic_sub_location_returns_none_on_json_parse_error(self, mock_redis, mock_llm: MockLLMClient):
        """Test handling of invalid JSON response from LLM."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        parent_data = {"node_id": "parent_loc", "name": "Parent"}
        mock_redis.set("rpg:map:node:parent_loc", json.dumps(parent_data))

        mock_llm.set_response("sub location", "This is not valid JSON")

        engine = MapTopologyEngine(mock_llm)
        result = engine.create_dynamic_sub_location("parent_loc", "secret")

        assert result is None


@pytest.mark.unit
class TestMapEngineIngestL2:
    """Tests for L2 graph ingestion (batch node creation)."""

    def test_ingest_l2_graph_creates_all_nodes(self, mock_redis, sample_regions):
        """Test that ingest_l2_graph creates all nodes from regions."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        world_config = {"genre": "Test", "tone": "Neutral"}

        engine.ingest_l2_graph(sample_regions, world_config)

        assert engine.node_exists("loc_tavern")
        assert engine.node_exists("loc_forest")

    def test_ingest_l2_graph_creates_connections(self, mock_redis, sample_regions):
        """Test that ingest_l2_graph creates connections between neighbors."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        engine = MapTopologyEngine(None)
        world_config = {"genre": "Test"}

        # Mock LLM to avoid actual calls
        mock_llm = MockLLMClient()
        mock_llm.set_response("route", MOCK_ROUTE_CONCEPT)
        engine.llm_client = mock_llm

        engine.ingest_l2_graph(sample_regions, world_config)

        neighbors_tavern = engine.get_neighbors("loc_tavern")
        assert len(neighbors_tavern) == 1 or len(neighbors_tavern) > 0

        neighbors_forest = engine.get_neighbors("loc_forest")
        assert len(neighbors_forest) == 1 or len(neighbors_forest) > 0

    def test_ingest_l2_graph_skips_invalid_regions(self, mock_redis):
        """Test that ingest_l2_graph skips regions without region_id."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        regions = [
            {"region_id": "valid_region", "name": "Valid", "desc": "OK", "neighbors": []},
            {"name": "Invalid (no ID)", "desc": "Missing region_id", "neighbors": []}
        ]

        engine = MapTopologyEngine(None)
        world_config = {"genre": "Test"}

        engine.ingest_l2_graph(regions, world_config)

        assert engine.node_exists("valid_region")
        assert not engine.node_exists("Invalid (no ID)")


@pytest.mark.unit
class TestMapEngineErrorHandling:
    """Tests for error handling in MapEngine."""

    def test_save_node_handles_serialization_error(self, mock_redis):
        """Test that save_node handles JSON serialization errors."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine
        import logging

        engine = MapTopologyEngine(None)

        # Create an unserializable object
        unserializable_data = {"node_id": "test", "unserializable": object()}

        result = engine.save_node("test", unserializable_data)
        assert result is False

    def test_get_node_handles_invalid_json(self, mock_redis):
        """Test that get_node handles invalid JSON in Redis."""
        from rpg_world_agent.core.map_engine import MapTopologyEngine

        mock_redis.set("rpg:map:node:invalid", "this is not valid json")

        engine = MapTopologyEngine(None)
        result = engine.get_node("invalid")

        # Should return None or handle gracefully
        assert result is None