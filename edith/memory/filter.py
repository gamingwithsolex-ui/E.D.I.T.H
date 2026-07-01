"""
Memory Filter & Structurer
───────────────────────────
Gate-keeps what enters ChromaDB and attaches structured metadata
to every memory that passes the filter.

Functions:
    should_store(text)       → bool
    classify_memory(text)    → dict with type, importance, tags
"""

import re

# ── Low-value patterns that should NEVER be stored ──────────────────────
_GREETING_PATTERNS = [
    r"^\s*(hi|hello|hey|yo|sup|howdy|hola|good\s*(morning|afternoon|evening|night))\s*[!.,?]*\s*$",
    r"^\s*(what'?s?\s*up|how\s*are\s*you|how'?s?\s*it\s*going)\s*[!.,?]*\s*$",
]

_FILLER_PATTERNS = [
    r"^\s*(ok|okay|sure|yeah|yep|yup|nah|nope|hmm+|huh|ah+|oh+|um+|uh+|mhm+|alright|right|cool|nice|great|fine|good|thanks|thank\s*you|thx|ty|lol|lmao|haha|hehe|wow|ooh|aight|bet|fr|no\s*worries)\s*[!.,?]*\s*$",
    r"^\s*(yes|no|maybe|idk|i\s*don'?t\s*know|nevermind|never\s*mind|nothing|nvm)\s*[!.,?]*\s*$",
    r"^\s*(what|huh|say\s*again|repeat\s*that|come\s*again)\s*[!?.,]*\s*$",
]

_COMMAND_PATTERNS = [
    r"^\s*(shutdown|shut\s*down|exit|quit|power\s*down|go\s*to\s*sleep|sleep|standby)\s*[!.,?]*\s*$",
    r"^\s*(stop|shut\s*up|be\s*quiet|silence|hush|pause|stop\s*(talking|speaking))\s*[!.,?]*\s*$",
    r"^\s*(goodbye|good\s*bye|good\s*night|bye|see\s*you|see\s*ya|go\s*dark)\s*[!.,?]*\s*$",
    r"^\s*(wake\s*up|edith|hey\s*edith|ok\s*edith|okay\s*edith|e\.?d\.?i\.?t\.?h\.?)\s*[!.,?]*\s*$",
    r"^\s*(open|close|launch|start|run)\s+\w+\s*$",  # simple app commands
]

# ── High-value signals that SHOULD be stored ────────────────────────────
_PREFERENCE_SIGNALS = [
    r"\bi\s+(like|love|enjoy|adore|prefer|hate|dislike|can'?t\s*stand|don'?t\s*like|detest)\b",
    r"\bmy\s+fav(ou?rite)?\b",
]

_PERSONAL_FACT_SIGNALS = [
    r"\bmy\s+name\s+is\b", r"\bi\s+am\b", r"\bi'?m\b",
    r"\bi\s+live\b", r"\bi\s+work\b", r"\bi\s+study\b",
    r"\bmy\s+age\b", r"\bi'?m\s+from\b", r"\bcall\s+me\b",
    r"\bmy\s+(email|phone|birthday|school|university|college|pet|dog|cat|car|setup)\b",
    r"\bi\s+(have|own|drive|speak|attend)\b",
]

_TECHNICAL_SIGNALS = [
    r"\b(python|java(script)?|typescript|rust|golang|c\+\+|react|vue|angular|node|django|flask|docker|kubernetes|aws|gcp|azure|git|api|database|sql|nosql|mongo|postgres|redis|linux|windows|mac|server|deploy|ci/?cd|devops)\b",
    r"\b(bug|error|fix|debug|compile|build|test|refactor|optimize|architecture|framework|library|package|module|function|class|variable|algorithm)\b",
    r"\b(project|repo|repository|codebase|branch|commit|merge|pull\s*request|pr|issue)\b",
]

_PROJECT_SIGNALS = [
    r"\b(i'?m\s+working\s+on|my\s+project|current\s+project|building|developing|creating)\b",
    r"\b(deadline|milestone|sprint|task|feature|roadmap|backlog|release|version|mvp)\b",
]

_EVENT_SIGNALS = [
    r"\b(today|yesterday|tomorrow|last\s+week|next\s+week|last\s+month|this\s+morning|tonight)\b",
    r"\b(meeting|interview|appointment|exam|presentation|event|conference|hackathon|demo)\b",
    r"\b(happened|occurred|scheduled|planned|finished|completed|started|began)\b",
]

_DECISION_SIGNALS = [
    r"\b(i\s+decided|i'?m\s+going\s+to|i\s+chose|i\s+picked|i'?ll\s+use|switching\s+to|migrating\s+to|moving\s+to)\b",
    r"\b(instead\s+of|rather\s+than|over|better\s+than|compared\s+to)\b",
]

_BEHAVIORAL_SIGNALS = [
    r"\b(always|never|usually|sometimes|every\s+time|whenever|tend\s+to|habit)\b",
    r"\b(be\s+professional|formal|casual|chill|explain\s+in\s+detail|keep\s+it\s+short|brief)\b",
]


def should_store(text: str) -> bool:
    """
    Determine whether a piece of text is worth storing in long-term memory.

    Returns True  → store it (high-value content)
    Returns False → discard it (noise / filler / commands)
    """
    if not text or not isinstance(text, str):
        return False

    cleaned = text.strip()

    # Reject very short inputs with no informational content
    if len(cleaned) < 4:
        return False

    low = cleaned.lower()

    # ── Stage 1: Reject known low-value patterns ────────────────────────
    for pattern in _GREETING_PATTERNS + _FILLER_PATTERNS + _COMMAND_PATTERNS:
        if re.match(pattern, low, re.IGNORECASE):
            return False

    # Reject if it's just 1-2 words and not a meaningful fact
    word_count = len(low.split())
    if word_count <= 2:
        # Allow very short but info-dense inputs like "I'm Amal"
        has_info = any(re.search(p, low) for p in _PERSONAL_FACT_SIGNALS)
        if not has_info:
            return False

    # ── Stage 2: Accept known high-value patterns ───────────────────────
    all_signals = (
        _PREFERENCE_SIGNALS + _PERSONAL_FACT_SIGNALS + _TECHNICAL_SIGNALS +
        _PROJECT_SIGNALS + _EVENT_SIGNALS + _DECISION_SIGNALS + _BEHAVIORAL_SIGNALS
    )
    for pattern in all_signals:
        if re.search(pattern, low, re.IGNORECASE):
            return True

    # ── Stage 3: Heuristic — longer statements with substance ───────────
    # If it has enough words and contains some nouns/verbs, it's likely worth keeping
    if word_count >= 8:
        return True

    # Default: don't store ambiguous short content
    return False


# ── Memory Type Classification ──────────────────────────────────────────

def _detect_type(text: str) -> str:
    """Classify memory into: semantic, episodic, working, or temporary."""
    low = text.lower()

    # Working memory — active tasks, current work
    working_patterns = [
        r"\b(i'?m\s+(working|building|developing|debugging|testing|coding|fixing|writing))\b",
        r"\b(currently|right\s+now|at\s+the\s+moment|in\s+progress)\b",
        r"\b(let\s+me|trying\s+to|need\s+to|going\s+to|about\s+to)\b",
    ]
    for p in working_patterns:
        if re.search(p, low):
            return "working"

    # Episodic memory — events tied to time
    episodic_patterns = [
        r"\b(today|yesterday|tomorrow|last\s+(week|month|year)|this\s+(morning|evening|week))\b",
        r"\b(happened|occurred|just\s+(did|finished|started|completed))\b",
        r"\b(meeting|interview|appointment|exam|event|conference)\b",
    ]
    for p in episodic_patterns:
        if re.search(p, low):
            return "episodic"

    # Temporary — questions, clarifications, transient
    temp_patterns = [
        r"^(what|how|why|where|when|who|can\s+you|could\s+you|do\s+you|is\s+there)\b",
        r"\b(just\s+wondering|quick\s+question|curious)\b",
    ]
    for p in temp_patterns:
        if re.search(p, low):
            return "temporary"

    # Default: semantic (factual knowledge)
    return "semantic"


def _score_importance(text: str) -> int:
    """Score importance from 1–10 based on content signals."""
    low = text.lower()
    score = 3  # baseline

    # Personal identity info → high value
    identity_patterns = [r"\bmy\s+name\b", r"\bi\s+am\b", r"\bi'?m\b", r"\bcall\s+me\b"]
    if any(re.search(p, low) for p in identity_patterns):
        score += 3

    # Preferences → moderately high
    if any(re.search(p, low) for p in _PREFERENCE_SIGNALS):
        score += 2

    # Technical decisions → high
    if any(re.search(p, low) for p in _TECHNICAL_SIGNALS):
        score += 2

    # Project context → high
    if any(re.search(p, low) for p in _PROJECT_SIGNALS):
        score += 2

    # Decisions → very high
    if any(re.search(p, low) for p in _DECISION_SIGNALS):
        score += 3

    # Events → moderate
    if any(re.search(p, low) for p in _EVENT_SIGNALS):
        score += 1

    # Corrections are very high value
    correction_patterns = [r"\b(no|wrong|incorrect|actually|not\s+right)\b", r"\bi\s+(said|meant)\b"]
    if any(re.search(p, low) for p in correction_patterns):
        score += 3

    # Length bonus — longer = more detail = more valuable
    word_count = len(low.split())
    if word_count >= 15:
        score += 1
    if word_count >= 25:
        score += 1

    return min(score, 10)


def _extract_tags(text: str) -> list:
    """Extract category tags from text content."""
    low = text.lower()
    tags = []

    tag_map = {
        "preference": _PREFERENCE_SIGNALS,
        "personal": _PERSONAL_FACT_SIGNALS,
        "technical": _TECHNICAL_SIGNALS,
        "project": _PROJECT_SIGNALS,
        "event": _EVENT_SIGNALS,
        "decision": _DECISION_SIGNALS,
        "behavioral": _BEHAVIORAL_SIGNALS,
    }

    for tag, patterns in tag_map.items():
        for p in patterns:
            if re.search(p, low, re.IGNORECASE):
                tags.append(tag)
                break  # one match per tag category is enough

    if not tags:
        tags.append("general")

    return tags


def classify_memory(text: str) -> dict:
    """
    Produce structured metadata for a memory entry.

    Returns:
        {
            "type": "semantic" | "episodic" | "working" | "temporary",
            "importance": 1-10,
            "tags": ["preference", "technical", ...]
        }
    """
    return {
        "type": _detect_type(text),
        "importance": _score_importance(text),
        "tags": _extract_tags(text),
    }
