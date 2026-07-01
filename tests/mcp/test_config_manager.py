import pytest
import os
import yaml
from edith.mcp.config.config_manager import ConfigManager

@pytest.fixture
def temp_config_file(tmp_path):
    config_data = {
        "mcp": {
            "defaults": {
                "api_key_env": "TEST_API_KEY",
                "timeout_seconds": 15
            },
            "servers": {
                "test_server": {
                    "url": "http://localhost",
                    "api_key_env": "CUSTOM_API_KEY"
                }
            }
        }
    }
    file_path = tmp_path / "mcp_servers.yaml"
    with open(file_path, "w") as f:
        yaml.dump(config_data, f)
    return str(file_path)

def test_config_manager_env_resolution(temp_config_file):
    os.environ["CUSTOM_API_KEY"] = "my_secret_key"
    
    mgr = ConfigManager(temp_config_file)
    config = mgr.load()
    
    server_cfg = mgr.get_server_config("test_server")
    assert server_cfg is not None
    assert server_cfg["api_key"] == "my_secret_key"
    assert server_cfg["timeout_seconds"] == 15
