import pytest
from unittest.mock import MagicMock
from edith.core.brain import EdithBrain
from edith.core.config import JarvisConfig

@pytest.mark.asyncio
async def test_brain_initialization(mock_bus, mock_engine):
    config = JarvisConfig()
    brain = EdithBrain(config=config, engine=mock_engine, bus=mock_bus)
    
    # Check that brain components are initialized
    assert brain._engine == mock_engine
    assert brain._bus == mock_bus
    assert brain._config == config

@pytest.mark.asyncio
async def test_brain_process_message_basic(mock_bus, mock_engine):
    config = JarvisConfig()
    brain = EdithBrain(config=config, engine=mock_engine, bus=mock_bus)
    
    response = await brain.process_message(
        message="Hello Edith",
        session_id="test_session"
    )
    
    assert response is not None
    # Our mock engine just returns "Mock response"
    assert response.get("content") == "Mock response"
