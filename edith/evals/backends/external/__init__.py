"""External-framework subprocess backends (Hermes Agent, OpenClaw)."""

from edith.evals.backends.external.hermes_agent import HermesBackend
from edith.evals.backends.external.openclaw import OpenClawBackend

__all__ = ["HermesBackend", "OpenClawBackend"]
