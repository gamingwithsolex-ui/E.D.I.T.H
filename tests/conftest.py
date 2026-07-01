import pytest
import os
import tempfile
import sqlite3
from pathlib import Path

# Set test environment variable so Edith uses test paths if needed
os.environ["EDITH_ENV"] = "test"

@pytest.fixture
def temp_db_path():
    """Provides a temporary SQLite database path that is cleaned up after the test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def temp_config_dir(tmp_path):
    """Provides a temporary config directory."""
    return tmp_path

@pytest.fixture
def mock_bus():
    """Provides an instance of EventBus."""
    from edith.core.events import EventBus
    return EventBus()

@pytest.fixture
def mock_engine():
    """Provides a mock inference engine."""
    from edith.engine._stubs import InferenceEngine
    from edith.core.types import Message
    from typing import Any, Dict, Sequence, AsyncIterator

    class MockEngine(InferenceEngine):
        engine_id = "mock_engine"
        is_cloud = False

        def __init__(self, responses: list[str] = None):
            self.responses = responses or ["Mock response"]
            self.call_count = 0

        def generate(self, messages: Sequence[Message], **kwargs: Any) -> Dict[str, Any]:
            resp = self.responses[self.call_count % len(self.responses)]
            self.call_count += 1
            return {
                "content": resp,
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                "model": "mock-model",
                "finish_reason": "stop",
                "cost_usd": 0.0,
                "ttft": 0.1,
            }

        async def stream(self, messages: Sequence[Message], **kwargs: Any) -> AsyncIterator[str]:
            resp = self.responses[self.call_count % len(self.responses)]
            self.call_count += 1
            words = resp.split(" ")
            for word in words:
                yield word + " "

    return MockEngine()
