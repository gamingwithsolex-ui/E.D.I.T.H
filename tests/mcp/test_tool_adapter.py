import pytest
from edith.mcp.tool_adapter import MCPToolWrapper

class DummyManager:
    async def get_client(self, server_name, config=None):
        class DummyClient:
            async def call_tool(self, name, args):
                return {"content": [{"text": "Success!"}]}
        return DummyClient()

def test_tool_adapter_success():
    manager = DummyManager()
    
    # We must configure permissions to allow it
    from edith.mcp.security.permissions import permission_engine, PermissionTier
    permission_engine.set_policy("dummy", "test_tool", PermissionTier.READ_ONLY)
    
    wrapper = MCPToolWrapper("dummy", "test_tool", manager)
    result = wrapper()
    
    assert result == "Success!"
