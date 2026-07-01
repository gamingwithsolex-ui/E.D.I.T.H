"""Operators — persistent, scheduled autonomous agents."""

from edith.operators.loader import load_operator
from edith.operators.manager import OperatorManager
from edith.operators.types import OperatorManifest

__all__ = ["OperatorManifest", "OperatorManager", "load_operator"]
