"""
Smart Retrieval System
─────────────────────
Multi-signal ranked retrieval from ChromaDB that combines:
  - Semantic similarity (from ChromaDB vector distance)
  - Importance score (from structured metadata)
  - Recency factor (exponential decay on timestamp)

Returns clean, deduplicated, formatted context — not raw dumps.

Functions:
    smart_retrieve(query, memory, n_results=5) → str
"""

import datetime
import math
import re

# ── Recency Decay ───────────────────────────────────────────────────────

# Half-life in days: after this many days, recency score drops to 0.5
_RECENCY_HALF_LIFE_DAYS = 7.0


def _parse_timestamp(time_str: str) -> float:
    """Parse an ISO timestamp string into a Unix timestamp. Returns 0 on failure."""
    if not time_str:
        return 0.0
    try:
        dt = datetime.datetime.fromisoformat(time_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def _recency_score(time_str: str) -> float:
    """
    Compute recency score using exponential decay.
    Returns 1.0 for just-now, decaying toward 0 for older entries.
    """
    ts = _parse_timestamp(time_str)
    if ts <= 0:
        return 0.3  # unknown time → low but not zero

    now = datetime.datetime.now().timestamp()
    age_days = max((now - ts) / 86400.0, 0.0)

    # Exponential decay: score = 2^(-age / half_life)
    decay = math.pow(2, -age_days / _RECENCY_HALF_LIFE_DAYS)
    return max(decay, 0.05)  # floor at 0.05 so old memories aren't completely invisible


# ── Importance Normalization ────────────────────────────────────────────

def _importance_score(metadata: dict) -> float:
    """
    Extract and normalize importance from metadata to [0, 1] range.
    Importance is stored as 1–10 integer.
    """
    if not metadata:
        return 0.3

    imp = metadata.get("importance", 3)
    if isinstance(imp, str):
        try:
            imp = int(imp)
        except ValueError:
            imp = 3
    elif not isinstance(imp, (int, float)):
        imp = 3

    # Normalize 1-10 → 0.0-1.0
    return max(min(imp / 10.0, 1.0), 0.0)


# ── Similarity Normalization ───────────────────────────────────────────

def _similarity_score(distance: float) -> float:
    """
    Convert ChromaDB distance to a similarity score in [0, 1].
    ChromaDB uses L2 distance by default — lower = more similar.
    """
    # Typical L2 distances range from 0 (identical) to ~2.0+ (very different)
    # Convert to similarity: 1 / (1 + distance)
    return 1.0 / (1.0 + distance)


# ── Deduplication ───────────────────────────────────────────────────────

def _deduplicate_results(results: list) -> list:
    """
    Remove near-duplicate results based on token overlap.
    Each result is a dict with 'text', 'score', etc.
    """
    if not results:
        return results

    _STOPWORDS = frozenset({
        "a", "an", "the", "is", "are", "was", "were", "i", "me", "my",
        "you", "your", "he", "she", "it", "they", "them", "to", "of",
        "in", "for", "on", "with", "at", "by", "from", "and", "but",
        "or", "so", "not", "user", "said", "edith", "replied",
    })

    def _tokens(text):
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        return set(w for w in words if w not in _STOPWORDS)

    deduplicated = []
    seen_token_sets = []

    for item in results:
        item_tokens = _tokens(item["text"])
        is_dup = False

        for existing_tokens in seen_token_sets:
            if not item_tokens or not existing_tokens:
                continue
            overlap = len(item_tokens & existing_tokens) / max(len(item_tokens | existing_tokens), 1)
            if overlap > 0.7:
                is_dup = True
                break

        if not is_dup:
            deduplicated.append(item)
            seen_token_sets.append(item_tokens)

    return deduplicated


# ── Main Retrieval Function ─────────────────────────────────────────────

# Weights for composite scoring
_W_SIMILARITY  = 0.50
_W_IMPORTANCE  = 0.30
_W_RECENCY     = 0.20


def smart_retrieve(query: str, memory, n_results: int = 5) -> str:
    """
    Perform ranked retrieval across ChromaDB collections.

    Searches compressed summaries first, then falls back to raw collections.
    Results are ranked by a composite score:
        final = 0.5 * similarity + 0.3 * importance + 0.2 * recency

    Args:
        query: The user's current query text
        memory: The Memory instance with ChromaDB collections
        n_results: Maximum number of results to return

    Returns:
        Formatted string of top relevant memories, ready for LLM context.
        Returns empty string if nothing relevant is found.
    """
    if not query or not memory.chroma_client:
        return ""

    all_candidates = []

    # How many raw results to pull from each collection before ranking
    fetch_n = max(n_results * 3, 10)

    # ── 1. Query compressed summaries (preferred) ───────────────────────
    if memory.compressed_coll:
        try:
            res = memory.compressed_coll.query(
                query_texts=[query],
                n_results=min(fetch_n, 20),
                include=["documents", "metadatas", "distances"],
            )
            if res and res.get("documents") and res["documents"][0]:
                docs = res["documents"][0]
                metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
                dists = res["distances"][0] if res.get("distances") else [1.0] * len(docs)

                for doc, meta, dist in zip(docs, metas, dists):
                    sim = _similarity_score(dist)
                    imp = _importance_score(meta)
                    rec = _recency_score(meta.get("time", "") if meta else "")

                    composite = (_W_SIMILARITY * sim) + (_W_IMPORTANCE * imp) + (_W_RECENCY * rec)

                    all_candidates.append({
                        "text": doc,
                        "score": composite,
                        "source": "compressed",
                        "sim": sim,
                        "imp": imp,
                        "rec": rec,
                    })
        except Exception as e:
            print(f"[RETRIEVE] Compressed query error: {e}")

    # ── 2. Query raw facts ──────────────────────────────────────────────
    if memory.facts_coll:
        try:
            res = memory.facts_coll.query(
                query_texts=[query],
                n_results=min(fetch_n, 15),
                include=["documents", "metadatas", "distances"],
            )
            if res and res.get("documents") and res["documents"][0]:
                docs = res["documents"][0]
                metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
                dists = res["distances"][0] if res.get("distances") else [1.0] * len(docs)

                for doc, meta, dist in zip(docs, metas, dists):
                    sim = _similarity_score(dist)
                    imp = _importance_score(meta)
                    rec = _recency_score(meta.get("time", "") if meta else "")

                    composite = (_W_SIMILARITY * sim) + (_W_IMPORTANCE * imp) + (_W_RECENCY * rec)

                    all_candidates.append({
                        "text": doc,
                        "score": composite,
                        "source": "facts",
                        "sim": sim,
                        "imp": imp,
                        "rec": rec,
                    })
        except Exception as e:
            print(f"[RETRIEVE] Facts query error: {e}")

    # ── 3. Query raw conversations ──────────────────────────────────────
    if memory.convo_coll:
        try:
            res = memory.convo_coll.query(
                query_texts=[query],
                n_results=min(fetch_n, 10),
                include=["documents", "metadatas", "distances"],
            )
            if res and res.get("documents") and res["documents"][0]:
                docs = res["documents"][0]
                metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
                dists = res["distances"][0] if res.get("distances") else [1.0] * len(docs)

                for doc, meta, dist in zip(docs, metas, dists):
                    sim = _similarity_score(dist)
                    imp = _importance_score(meta)
                    rec = _recency_score(meta.get("time", "") if meta else "")

                    composite = (_W_SIMILARITY * sim) + (_W_IMPORTANCE * imp) + (_W_RECENCY * rec)

                    # Slightly discount raw conversation entries
                    # (they tend to be noisy compared to facts/compressed)
                    composite *= 0.9

                    all_candidates.append({
                        "text": doc,
                        "score": composite,
                        "source": "conversations",
                        "sim": sim,
                        "imp": imp,
                        "rec": rec,
                    })
        except Exception as e:
            print(f"[RETRIEVE] Conversations query error: {e}")

    # ── 4. Rank, deduplicate, and format ────────────────────────────────
    if not all_candidates:
        return ""

    # Sort by composite score (descending)
    all_candidates.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate
    all_candidates = _deduplicate_results(all_candidates)

    # Take top N
    top = all_candidates[:n_results]

    # Format output
    lines = []
    for item in top:
        text = item["text"].strip()
        # Truncate very long entries
        if len(text) > 300:
            text = text[:297] + "..."
        lines.append(f"  - {text}")

    return "\n".join(lines)
