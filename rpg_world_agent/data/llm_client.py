"""LLM Client Factory - Centralized LLM client management.

This module provides a singleton factory for creating and managing
OpenAI-compatible LLM clients used throughout the RPG engine.
"""

from typing import Optional

# Try to import openai, fall back to mock for local development
try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    from rpg_world_agent.data.mock_openai import OpenAI as MockOpenAI
    OpenAI = MockOpenAI
    _openai_available = False

from rpg_world_agent.config.settings import AGENT_CONFIG


class LLMClientFactory:
    """
    Singleton factory for LLM client instances.

    Ensures that only one client instance is created per configuration,
    reducing connection overhead and maintaining consistency across the application.
    """

    _instance = None

    @classmethod
    def get_client(cls):
        """
        Get or create the LLM client instance.

        Returns:
            OpenAI client instance configured with settings from AGENT_CONFIG.

        Raises:
            ConnectionError: If the LLM API endpoint is misconfigured.
        """
        if cls._instance is None:
            llm_config = AGENT_CONFIG.get("llm", {})

            base_url = llm_config.get("base_url", "http://localhost:11434/v1")
            api_key = llm_config.get("api_key", "sk-xxx")
            timeout = llm_config.get("timeout", 120)

            cls._instance = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout,
            )

            print(f"🤖 LLM Client initialized: {base_url}")

        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the client instance. Useful for testing or reconfiguration."""
        cls._instance = None
        print("🔄 LLM Client reset.")

    @classmethod
    def get_config(cls) -> dict:
        """Get the current LLM configuration from AGENT_CONFIG."""
        return AGENT_CONFIG.get("llm", {})


# Convenience function for quick access
def get_llm_client():
    """Get the LLM client instance (alias for LLMClientFactory.get_client)."""
    return LLMClientFactory.get_client()
