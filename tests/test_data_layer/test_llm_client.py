"""
Unit tests for LLMClientFactory.
"""

import pytest
from unittest.mock import MagicMock, patch

from tests.mocks.llm_mock import MockLLMClient, create_mock_llm_client


@pytest.mark.unit
class TestLLMClientSingleton:
    """Tests for LLM client singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Test that get_client returns the same instance."""
        from rpg_world_agent.data.llm_client import LLMClientFactory

        # Reset singleton
        LLMClientFactory._instance = None

        with patch('rpg_world_agent.data.llm_client.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            instance1 = LLMClientFactory.get_client()
            instance2 = LLMClientFactory.get_client()

            assert instance1 is instance2
            mock_openai.assert_called_once()

    def test_reset_clears_singleton(self):
        """Test that reset clears the singleton instance."""
        from rpg_world_agent.data.llm_client import LLMClientFactory

        # Reset singleton
        LLMClientFactory._instance = None

        with patch('rpg_world_agent.data.llm_client.OpenAI') as mock_openai:
            mock_client1 = MagicMock()
            mock_client2 = MagicMock()
            mock_openai.return_value = mock_client1

            instance1 = LLMClientFactory.get_client()
            instance1_is_reset = LLMClientFactory._instance

            LLMClientFactory.reset()

            assert LLMClientFactory._instance is None
            assert instance1_is_reset is not None

    def test_reset_creates_new_instance(self):
        """Test that reset allows creating a new instance."""
        from rpg_world_agent.data.llm_client import LLMClientFactory

        LLMClientFactory._instance = None

        with patch('rpg_world_agent.data.llm_client.OpenAI') as mock_openai:
            mock_client1 = MagicMock()
            mock_client2 = MagicMock()
            mock_openai.return_value = mock_client1

            instance1 = LLMClientFactory.get_client()

            LLMClientFactory.reset()

            mock_openai.return_value = mock_client2
            instance2 = LLMClientFactory.get_client()

            assert instance1 is not instance2
            assert mock_openai.call_count == 2

    def test_get_config_returns_llm_config(self):
        """Test that get_config returns the LLM configuration."""
        from rpg_world_agent.data.llm_client import LLMClientFactory
        from rpg_world_agent.config import settings

        config = LLMClientFactory.get_config()

        assert isinstance(config, dict)
        assert "base_url" in config or config == {}


@pytest.mark.unit
class TestLLMClientConfiguration:
    """Tests for LLM client configuration."""

    def test_client_uses_agent_config_base_url(self):
        """Test that client uses base_url from AGENT_CONFIG."""
        from rpg_world_agent.data.llm_client import LLMClientFactory

        LLMClientFactory._instance = None

        test_config = {
            "llm": {
                "base_url": "http://test-llm:11434/v1",
                "api_key": "test-key",
                "timeout": 60
            }
        }

        with patch('rpg_world_agent.data.llm_client.AGENT_CONFIG', test_config):
            with patch('rpg_world_agent.data.llm_client.OpenAI') as mock_openai:
                LLMClientFactory.get_client()

                call_kwargs = mock_openai.call_args[1]
                assert call_kwargs['base_url'] == "http://test-llm:11434/v1"
                assert call_kwargs['api_key'] == "test-key"
                assert call_kwargs['timeout'] == 60
        # Reset singleton
        LLMClientFactory._instance = None

    def test_client_uses_default_values_for_missing_config(self):
        """Test that client uses defaults when config is missing."""
        from rpg_world_agent.data.llm_client import LLMClientFactory

        LLMClientFactory._instance = None

        test_config = {
            "llm": {}
        }

        with patch('rpg_world_agent.data.llm_client.AGENT_CONFIG', test_config):
            with patch('rpg_world_agent.data.llm_client.OpenAI') as mock_openai:
                LLMClientFactory.get_client()

                call_kwargs = mock_openai.call_args[1]
                assert call_kwargs['base_url'] == "http://localhost:11434/v1"
                assert call_kwargs['api_key'] == "sk-xxx"
                assert call_kwargs['timeout'] == 120
        # Reset singleton
        LLMClientFactory._instance = None


@pytest.mark.unit
class TestGetLLMClientFunction:
    """Tests for the get_llm_client convenience function."""

    def test_get_llm_client_returns_factory_instance(self):
        """Test that get_llm_client returns the same as factory.get_client."""
        from rpg_world_agent.data.llm_client import LLMClientFactory, get_llm_client

        LLMClientFactory._instance = None

        with patch('rpg_world_agent.data.llm_client.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            factory_instance = LLMClientFactory.get_client()
            function_instance = get_llm_client()

            assert factory_instance is function_instance


@pytest.mark.unit
class TestMockLLMClient:
    """Tests for the MockLLMClient utility."""

    def test_mock_client_default_response(self):
        """Test that mock client returns default response."""
        mock_client = create_mock_llm_client()
        mock_client.default_response = "Default test response"

        response = mock_client.chat.completions.create(
            model="test-model",
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert response.choices[0].message.content == "Default test response"

    def test_mock_client_pattern_response(self):
        """Test that mock client recognizes pattern-based responses."""
        mock_client = create_mock_llm_client()
        mock_client.set_response("pattern", "Pattern matched!")

        response = mock_client.chat.completions.create(
            model="test-model",
            messages=[{"role": "user", "content": "This has pattern in it"}]
        )

        assert response.choices[0].message.content == "Pattern matched!"

    def test_mock_client_call_count_tracking(self):
        """Test that mock client tracks call count."""
        mock_client = create_mock_llm_client()

        mock_client.chat.completions.create(model="test", messages=[{"role": "user", "content": "1"}])
        mock_client.chat.completions.create(model="test", messages=[{"role": "user", "content": "2"}])

        assert mock_client.call_count == 2

    def test_mock_client_call_history(self):
        """Test that mock client records call history."""
        mock_client = create_mock_llm_client()

        mock_client.chat.completions.create(
            model="test-model",
            messages=[{"role": "user", "content": "test message"}],
            temperature=0.5,
            max_tokens=100
        )

        assert len(mock_client.call_history) == 1
        last_call = mock_client.get_last_call_kwargs()
        assert last_call['model'] == "test-model"
        assert last_call['temperature'] == 0.5
        assert last_call['max_tokens'] == 100

    def test_mock_client_reset(self):
        """Test that mock client reset clears history."""
        mock_client = create_mock_llm_client()

        mock_client.chat.completions.create(model="test", messages=[{"role": "user", "content": "test"}])
        mock_client.reset()

        assert mock_client.call_count == 0
        assert len(mock_client.call_history) == 0

    def test_mock_client_error_on_call(self):
        """Test that mock client can raise errors on call."""
        mock_client = create_mock_llm_client()
        mock_client.raise_error_on_call = ConnectionError("Test error")

        with pytest.raises(ConnectionError, match="Test error"):
            mock_client.chat.completions.create(model="test", messages=[{"role": "user", "content": "test"}])

    def test_mock_client_longest_pattern_match(self):
        """Test that mock client matches the longest pattern."""
        mock_client = create_mock_llm_client()
        mock_client.set_response("cat", "cat response")
        mock_client.set_response("category", "category response")
        mock_client.set_response("category test", "category test response")

        response = mock_client.chat.completions.create(
            model="test",
            messages=[{"role": "user", "content": "This is a category test message"}]
        )

        # Should match longest pattern "category test"
        assert response.choices[0].message.content == "category test response"