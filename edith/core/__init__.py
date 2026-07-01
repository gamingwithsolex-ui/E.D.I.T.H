import os
from pydantic import BaseModel, Field

class EdithConfig(BaseModel):
    """
    Configuration model for E.D.I.T.H.
    Loads configurations from system environment variables with smart defaults.
    """
    host: str = Field(default="127.0.0.1", description="Server interface host")
    port: int = Field(default=8080, description="Server port to bind to")
    env: str = Field(default="development", description="Operational environment name")
    daemon_mode: bool = Field(default=False, description="Whether to run in daemon mode")
    model_provider: str = Field(default="google", description="Default LLM provider (google | openai)")
    log_level: str = Field(default="INFO", description="Global logging level")

class BaseAgent:
    """
    Abstract base class representing an E.D.I.T.H. agent instance.
    All specialized agents (hybrid, Claude runner, etc.) inherit from this.
    """
    def __init__(self, name: str, version: str = "0.1.0"):
        self.name = name
        self.version = version
        self.active = True

    def register_tool(self, tool_func):
        """
        Registers a custom tool function for this agent.
        """
        raise NotImplementedError("Subclasses must implement register_tool")

    async def execute_task(self, task_description: str) -> str:
        """
        Processes a prompt task description asynchronously.
        """
        raise NotImplementedError("Subclasses must implement execute_task")
