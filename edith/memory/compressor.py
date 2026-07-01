"""
Context Compression Engine
──────────────────────────
Periodically consolidates ChromaDB memories:
  - Groups similar memories by tag + token overlap
  - Removes near-duplicate entries
  - Merges related clusters into compressed summaries
  - Stores summaries in `edith_compressed` collection

Functions:
    compress_memories(memory)  → dict with merge stats
"""

import re
import time
import datetime
import uuid


# ── Similarity Helpers ──────────────────────────────────────────────────

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
    "they", "them", "his", "her", "its", "this", "that", "these", "those",
    "am", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "and", "but", "or", "so", "if", "then", "than", "too", "very",
    "not", "no", "just", "also", "about", "up", "out", "into", "over",
    "some", "any", "all", "each", "every", "both", "few", "more", "most",
    "said", "user", "edith", "replied",
})


def _tokenize(text: str) -> set:
    """Extract meaningful lowercase tokens from text."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _normalized_similarity(text_a: str, text_b: str) -> float:
    """
    Character-level similarity ratio (cheap near-duplicate detection).
    Uses sorted-token comparison to be order-independent.
    """
    tokens_a = sorted(_tokenize(text_a))
    tokens_b = sorted(_tokenize(text_b))
    str_a = " ".join(tokens_a)
    str_b = " ".join(tokens_b)

    if not str_a or not str_b:
        return 0.0

    # Simple ratio based on common subsequence length
    len_a, len_b = len(str_a), len(str_b)
    max_len = max(len_a, len_b)
    if max_len == 0:
        return 1.0

    # Count matching characters (order-insensitive at token level)
    common_tokens = set(tokens_a) & set(tokens_b)
    total_tokens = set(tokens_a) | set(tokens_b)
    if not total_tokens:
        return 1.0
    return len(common_tokens) / len(total_tokens)


# ── Clustering ──────────────────────────────────────────────────────────

def _group_by_similarity(documents: list, metadatas: list, threshold: float = 0.40) -> list:
    """
    Group documents into clusters based on token-set similarity.
    Returns list of clusters, each cluster is a list of (index, doc, metadata) tuples.

    Uses single-linkage clustering: a document joins a cluster if it
    is similar enough to ANY existing member.
    """
    if not documents:
        return []

    token_sets = [_tokenize(doc) for doc in documents]
    n = len(documents)
    assigned = [False] * n
    clusters = []

    for i in range(n):
        if assigned[i]:
            continue

        # Start a new cluster with document i
        cluster = [(i, documents[i], metadatas[i] if metadatas else {})]
        assigned[i] = True
        # Find all documents similar to this cluster
        changed = True
        while changed:
            changed = False
            for j in range(n):
                if assigned[j]:
                    continue
                # True single-linkage: compare against each individual cluster member's tokens
                max_sim = 0.0
                for member_idx, _, _ in cluster:
                    sim = _jaccard_similarity(token_sets[member_idx], token_sets[j])
                    if sim > max_sim:
                        max_sim = sim
                if max_sim >= threshold:
                    cluster.append((j, documents[j], metadatas[j] if metadatas else {}))
                    assigned[j] = True
                    changed = True

        clusters.append(cluster)

    return clusters


# ── Deduplication ───────────────────────────────────────────────────────

def _find_duplicates(documents: list, dup_threshold: float = 0.85) -> set:
    """
    Find indices of near-duplicate documents.
    For each pair of duplicates, marks the earlier (older) one for removal.
    Returns set of indices to remove.
    """
    remove_indices = set()
    n = len(documents)

    for i in range(n):
        if i in remove_indices:
            continue
        for j in range(i + 1, n):
            if j in remove_indices:
                continue
            sim = _normalized_similarity(documents[i], documents[j])
            if sim >= dup_threshold:
                # Keep the later entry (j), remove the earlier one (i)
                remove_indices.add(i)
                break

    return remove_indices


# ── Summary Generation ──────────────────────────────────────────────────

def _generate_summary(cluster: list) -> str:
    """
    Generate a compressed summary from a cluster of related memory entries.

    Args:
        cluster: list of (index, document_text, metadata) tuples

    Returns:
        A single concise summary string.
    """
    if len(cluster) == 1:
        return cluster[0][1]  # single entry, return as-is

    # Extract all unique meaningful facts
    all_facts = []
    seen_tokens = set()

    for _, doc, _ in cluster:
        # Split into sentences
        sentences = re.split(r"[.!?\n]+", doc)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue

            tokens = _tokenize(sentence)
            # Only add if this sentence brings new information
            new_tokens = tokens - seen_tokens
            if len(new_tokens) >= 2 or (len(tokens) > 0 and len(new_tokens) / max(len(tokens), 1) > 0.3):
                all_facts.append(sentence)
                seen_tokens |= tokens

    if not all_facts:
        # Fallback: just take the longest entry
        longest = max(cluster, key=lambda x: len(x[1]))
        return longest[1]

    # Build summary
    # Extract the dominant tags from metadata
    all_tags = set()
    for _, _, meta in cluster:
        if isinstance(meta, dict):
            tags = meta.get("tags", "")
            if isinstance(tags, str) and tags:
                all_tags.update(t.strip() for t in tags.split(","))
            elif isinstance(tags, list):
                all_tags.update(tags)

    tag_prefix = ""
    if all_tags:
        tag_prefix = f"[{', '.join(sorted(all_tags))}] "

    # Combine facts, limit to avoid bloat
    combined_facts = all_facts[:8]  # max 8 unique facts per summary
    summary = tag_prefix + ". ".join(combined_facts)

    # Clean up
    summary = re.sub(r"\s+", " ", summary).strip()
    if not summary.endswith("."):
        summary += "."

    return summary


# ── Importance Aggregation ──────────────────────────────────────────────

def _aggregate_importance(cluster: list) -> int:
    """
    Compute the importance of a compressed summary from its source cluster.
    Takes the max importance + small bonus for cluster size.
    """
    importances = []
    for _, _, meta in cluster:
        if isinstance(meta, dict):
            imp = meta.get("importance", 3)
            if isinstance(imp, (int, float)):
                importances.append(int(imp))
            elif isinstance(imp, str):
                try:
                    importances.append(int(imp))
                except ValueError:
                    importances.append(3)

    if not importances:
        return 5

    max_imp = max(importances)
    # Bonus: larger clusters = more evidence = slightly more important
    size_bonus = min(len(cluster) - 1, 2)  # max +2 bonus
    return min(max_imp + size_bonus, 10)


def _aggregate_tags(cluster: list) -> str:
    """Merge all tags from a cluster into a comma-separated string."""
    all_tags = set()
    for _, _, meta in cluster:
        if isinstance(meta, dict):
            tags = meta.get("tags", "")
            if isinstance(tags, str) and tags:
                all_tags.update(t.strip() for t in tags.split(","))
            elif isinstance(tags, list):
                all_tags.update(tags)
    return ",".join(sorted(all_tags)) if all_tags else "general"


# ── Main Compression Function ──────────────────────────────────────────

def compress_memories(memory) -> dict:
    """
    Run the full compression pipeline on ChromaDB memory collections.

    Steps:
        1. Pull all entries from facts + conversations collections
        2. Remove near-duplicates
        3. Cluster remaining entries by similarity
        4. For clusters with 3+ members, generate compressed summaries
        5. Store summaries in `edith_compressed` collection
        6. Purge source entries that were compressed

    Args:
        memory: The Memory instance (must have chroma collections initialized)

    Returns:
        dict with stats: {"merged": N, "removed_dupes": M, "compressed_summaries": K}
    """
    stats = {"merged": 0, "removed_dupes": 0, "compressed_summaries": 0, "errors": []}

    if not memory.chroma_client:
        stats["errors"].append("ChromaDB not available")
        return stats

    # Ensure compressed collection exists
    if not memory.compressed_coll:
        try:
            memory.compressed_coll = memory.chroma_client.get_or_create_collection("edith_compressed")
        except Exception as e:
            stats["errors"].append(f"Could not create compressed collection: {e}")
            return stats

    # ── Process each collection ─────────────────────────────────────────
    collections_to_process = []
    if memory.facts_coll:
        collections_to_process.append(("facts", memory.facts_coll))
    if memory.convo_coll:
        collections_to_process.append(("conversations", memory.convo_coll))

    for coll_name, collection in collections_to_process:
        try:
            result = collection.get(include=["documents", "metadatas"])
            if not result or not result.get("documents"):
                continue

            documents = result["documents"]
            metadatas = result.get("metadatas", [{}] * len(documents))
            ids = result["ids"]

            if len(documents) < 3:
                continue  # not enough entries to compress

            # Step 1: Find and remove duplicates
            dup_indices = _find_duplicates(documents)
            if dup_indices:
                dup_ids = [ids[i] for i in dup_indices]
                try:
                    collection.delete(ids=dup_ids)
                    stats["removed_dupes"] += len(dup_ids)
                    print(f"[COMPRESS] Removed {len(dup_ids)} duplicates from {coll_name}")
                except Exception as e:
                    stats["errors"].append(f"Dedup delete error ({coll_name}): {e}")

                # Filter out removed entries for clustering
                keep_mask = [i not in dup_indices for i in range(len(documents))]
                documents = [d for d, keep in zip(documents, keep_mask) if keep]
                metadatas = [m for m, keep in zip(metadatas, keep_mask) if keep]
                ids = [id_ for id_, keep in zip(ids, keep_mask) if keep]

            if len(documents) < 3:
                continue

            # Step 2: Cluster by similarity
            clusters = _group_by_similarity(documents, metadatas)

            # Step 3: Compress clusters with 3+ members
            ids_to_purge = []
            for cluster in clusters:
                if len(cluster) < 3:
                    continue  # leave small clusters as-is

                summary = _generate_summary(cluster)
                importance = _aggregate_importance(cluster)
                tags = _aggregate_tags(cluster)

                # Store compressed summary
                comp_id = f"comp_{coll_name}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
                try:
                    memory.compressed_coll.add(
                        documents=[summary],
                        metadatas=[{
                            "type": "semantic",
                            "importance": str(importance),
                            "tags": tags,
                            "source_collection": coll_name,
                            "source_count": str(len(cluster)),
                            "time": datetime.datetime.now().isoformat(),
                            "compressed": "true",
                        }],
                        ids=[comp_id],
                    )
                    stats["compressed_summaries"] += 1
                    stats["merged"] += len(cluster)
                    print(f"[COMPRESS] Merged {len(cluster)} {coll_name} entries → 1 compressed summary")
                except Exception as e:
                    stats["errors"].append(f"Compressed store error: {e}")
                    continue

                # Mark source entries for purge
                for idx, _, _ in cluster:
                    # idx is the position in the filtered list
                    if idx < len(ids):
                        ids_to_purge.append(ids[idx])

            # Step 4: Purge source entries that were compressed
            if ids_to_purge:
                try:
                    collection.delete(ids=ids_to_purge)
                    print(f"[COMPRESS] Purged {len(ids_to_purge)} source entries from {coll_name}")
                except Exception as e:
                    stats["errors"].append(f"Purge error ({coll_name}): {e}")

        except Exception as e:
            stats["errors"].append(f"Collection processing error ({coll_name}): {e}")

    # ── Summary ─────────────────────────────────────────────────────────
    total = stats["removed_dupes"] + stats["merged"]
    if total > 0:
        print(f"[COMPRESS] Compression complete: {stats['removed_dupes']} dupes removed, "
              f"{stats['merged']} entries merged into {stats['compressed_summaries']} summaries.")
    else:
        print("[COMPRESS] No compression needed — memory is already clean.")

    return stats
