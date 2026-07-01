import pytest
import os
from edith.mcp.registry_bridge import bootstrap_composio_mcp
from edith.tools.executor import TOOL_REGISTRY

def test_registry_bridge_kill_switch():
    os.environ["MCP_ENABLED"] = "false"
    
    config = {
        "servers": {
            "test_server": {}
        }
    }
    
    initial_count = len(TOOL_REGISTRY)
    bootstrap_composio_mcp(config)
    
    # Should not add anything
    assert len(TOOL_REGISTRY) == initial_count
    
    # Clean up
    del os.environ["MCP_ENABLED"]
