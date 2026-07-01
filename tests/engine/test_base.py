import pytest
from edith.core.types import Message

@pytest.mark.asyncio
async def test_mock_engine_generate(mock_engine):
    messages = [Message(role="user", content="Hello")]
    
    result = mock_engine.generate(messages, model="test")
    
    assert result["content"] == "Mock response"
    assert result["usage"]["total_tokens"] == 20
    assert result["model"] == "mock-model"

@pytest.mark.asyncio
async def test_mock_engine_stream(mock_engine):
    messages = [Message(role="user", content="Hello")]
    
    tokens = []
    async for token in mock_engine.stream(messages, model="test"):
        tokens.append(token)
        
    assert "".join(tokens) == "Mock response "
