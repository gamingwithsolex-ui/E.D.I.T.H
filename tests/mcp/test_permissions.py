import pytest
from edith.mcp.security.permissions import PermissionEngine, PermissionTier

def test_permission_evaluation():
    engine = PermissionEngine()
    engine.set_policy("gmail", "read_email", PermissionTier.READ_ONLY)
    engine.set_policy("gmail", "send_email", PermissionTier.DESTRUCTIVE)
    
    # READ_ONLY allows execution
    assert engine.evaluate("gmail", "read_email", {}) is True
    
    # DESTRUCTIVE fails in test (auto-deny)
    assert engine.evaluate("gmail", "send_email", {}) is False
    
    # Unknown tool defaults to DESTRUCTIVE
    assert engine.evaluate("gmail", "unknown_tool", {}) is False
