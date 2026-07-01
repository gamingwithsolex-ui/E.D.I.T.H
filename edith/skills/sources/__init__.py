"""Skill source resolvers — Hermes, OpenClaw, generic GitHub."""

from edith.skills.sources.base import ResolvedSkill, SourceResolver
from edith.skills.sources.github import GitHubResolver
from edith.skills.sources.hermes import HERMES_REPO_URL, HermesResolver
from edith.skills.sources.openclaw import OPENCLAW_REPO_URL, OpenClawResolver

__all__ = [
    "GitHubResolver",
    "HERMES_REPO_URL",
    "HermesResolver",
    "OPENCLAW_REPO_URL",
    "OpenClawResolver",
    "ResolvedSkill",
    "SourceResolver",
]
