"""Mock LLM client for testing."""

from typing import Dict, List, Optional
from unittest.mock import MagicMock
from dataclasses import dataclass


@dataclass
class MockChoice:
    message: MagicMock


@dataclass
class MockResponse:
    choices: List[MockChoice]


class MockLLMClient:
    """
    Mock LLM client for testing.
    Allows configurable responses for different prompts.
    """

    def __init__(self, default_response: str = "Mock response"):
        self.default_response = default_response
        self.prompt_responses: Dict[str, str] = {}
        self.call_count = 0
        self.call_history: List[tuple] = []

        # Mock chat completions
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = self._mock_completions_create

        # Mock for raise_on_call to simulate errors
        self.raise_error_on_call: Optional[Exception] = None

    def set_response(self, pattern: str, response: str) -> None:
        """Set a specific response for prompts containing the pattern."""
        self.prompt_responses[pattern] = response

    def _mock_completions_create(self, **kwargs) -> MockResponse:
        """Mock function for chat.completions.create."""
        self.call_count += 1
        self.call_history.append(kwargs)

        if self.raise_error_on_call:
            raise self.raise_error_on_call

        messages = kwargs.get("messages", [])
        prompt = ""
        for msg in messages:
            prompt += msg.get("content", "")

        # Check for specific pattern responses - sort by length (longest first) for longest match
        for pattern, response in sorted(
            self.prompt_responses.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if pattern in prompt:
                return MockResponse(
                    choices=[MockChoice(message=MagicMock(content=response))]
                )

        # Use default response
        return MockResponse(
            choices=[MockChoice(message=MagicMock(content=self.default_response))]
        )

    def reset(self) -> None:
        """Reset call history and counters."""
        self.call_count = 0
        self.call_history = []
        self.raise_error_on_call = None

    def get_last_call_kwargs(self) -> Optional[Dict]:
        """Get the kwargs from the last call."""
        if self.call_history:
            return self.call_history[-1]
        return None


def create_mock_llm_client() -> MockLLMClient:
    """Factory function to create a mock LLM client."""
    return MockLLMClient()


# Pre-configured mock responses for common scenarios
MOCK_INTENT_EXPLORE = '{"intent": "EXPLORE", "keyword": "secret door"}'
MOCK_INTENT_ACTION = '{"intent": "ACTION", "keyword": "attack"}'
MOCK_INTENT_CHAT = '{"intent": "CHAT", "keyword": "hello"}'
MOCK_ROUTE_CONCEPT = """{
    "route_name": "Hidden Passage",
    "geo_type": "Underground Tunnel",
    "description": "A dark, damp tunnel that smells of mold and stale water.",
    "risk_level": 2,
    "rumors": ["Something howls in the darkness"]
}"""
MOCK_DYNAMIC_LOCATION = """{
    "name": "Secret Vault",
    "desc": "A small room filled with old documents.",
    "geo_feature": "Underground Chamber",
    "risk_level": 1,
    "connection_path_name": "Rusty Ladder"
}"""
MOCK_NARRATIVE = "You see: Old wooden beams, cobwebs in corners, a flickering candle on a dusty table."