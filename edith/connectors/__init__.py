"""Data source connectors for Deep Research."""

from edith.connectors._stubs import (
    Attachment,
    BaseConnector,
    Document,
    SyncStatus,
)
from edith.connectors.store import KnowledgeStore

__all__ = ["Attachment", "BaseConnector", "Document", "KnowledgeStore", "SyncStatus"]

# Auto-register built-in connectors
import edith.connectors.obsidian  # noqa: F401

try:
    import edith.connectors.gmail  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.gmail_imap  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.gdrive  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import edith.connectors.notion  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.granola  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.gcontacts  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.imessage  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.apple_notes  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.apple_music  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.apple_contacts  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.slack_connector  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.outlook  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.gcalendar  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.dropbox  # noqa: F401
except ImportError:
    pass  # httpx may not be installed

try:
    import edith.connectors.whatsapp  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.oura  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.apple_health  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.strava  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.spotify  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.google_tasks  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.weather  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.github_notifications  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.hackernews  # noqa: F401
except ImportError:
    pass

try:
    import edith.connectors.news_rss  # noqa: F401
except ImportError:
    pass
