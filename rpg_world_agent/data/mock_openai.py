"""Mock OpenAI module for local development."""

from typing import List, Dict, Any, Optional

class MockMessage:
    """Mock message."""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

class MockChoice:
    """Mock choice."""
    def __init__(self, message: MockMessage):
        self.message = message

class MockCompletion:
    """Mock completion."""
    def __init__(self, content: str):
        self.choices = [MockChoice(MockMessage('assistant', content))]

class MockChatCompletions:
    """Mock chat completions API."""
    def create(self, model: str, messages: List[Dict[str, str]], 
                temperature: float = 0.7, max_tokens: int = 2000, **kwargs):
        """Create a mock completion."""
        # Simple echo response
        user_input = messages[-1]['content'] if messages else ''
        response = f"I received your input: '{user_input}'. This is a mock response."
        return MockCompletion(response)

class MockOpenAI:
    """Mock OpenAI client."""
    def __init__(self, base_url: str = '', api_key: str = '', **kwargs):
        self.base_url = base_url
        self.api_key = api_key
        self.chat = type('Chat', (), {})()  # Mock chat namespace
        self.chat.completions = MockChatCompletions()

def OpenAI(*args, **kwargs):
    """Factory function for creating MockOpenAI instances."""
    return MockOpenAI(*args, **kwargs)
