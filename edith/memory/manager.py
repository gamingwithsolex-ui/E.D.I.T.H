import json
import time
import datetime
import re
from edith.config import MEMORY_FILE, CHROMA_DIR, CONVO_LOG_DIR
from edith.memory.filter import should_store, classify_memory
from edith.memory.retrieval import smart_retrieve
from edith.memory.compressor import compress_memories as _run_compression

try:
    import chromadb
    CHROMA_OK = True
except ImportError:
    CHROMA_OK = False

class Memory:
    def __init__(self):
        self.data = {
            "last_seen": None,
            "session_count": 0,
            "alarms": [],
            "user_profile": {
                "name": None,
                "preferences": {},
                "interests": [],
                "skills": [],
                "location": None,
                "occupation": None,
                "personality_notes": [],
            },
            "topic_freq": {},
            "conversations": [],
            "interaction_style": {
                "prefers_detail": False,
                "prefers_humor": True,
                "formality": "casual",
            },
        }
        self._load_json()
        self._session_log = []
        
        self.chroma_client = None
        self.facts_coll = None
        self.notes_coll = None
        self.corrections_coll = None
        self.convo_coll = None
        self.compressed_coll = None
        
        # Exchange counter for periodic compression
        self._exchange_count = 0
        self._compress_every = 50
        
        if CHROMA_OK:
            try:
                # Use a more robust initialization with settings if needed
                self.chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
                # Facts: Long-term learned information
                self.facts_coll = self.chroma_client.get_or_create_collection("edith_facts")
                # Notes: Explicit user-created notes
                self.notes_coll = self.chroma_client.get_or_create_collection("edith_notes")
                # Corrections: When user says "No, I meant X"
                self.corrections_coll = self.chroma_client.get_or_create_collection("edith_corrections")
                # Conversations history: Every exchange stored as vector data
                self.convo_coll = self.chroma_client.get_or_create_collection("edith_conversations_history")
                # Compressed summaries: Merged/deduplicated memory
                self.compressed_coll = self.chroma_client.get_or_create_collection("edith_compressed")
                print("[MEM] ChromaDB Neural Link established (with compression layer).")
            except Exception as e:
                print(f"[MEM] ChromaDB Neural Link failure: {e}. Defaulting to JSON storage.")
        else:
            print("[MEM] ChromaDB not detected. Vector search disabled. Run: pip install chromadb")
            
        self.data.setdefault("facts", [])
        self.data.setdefault("notes", [])
        self.data.setdefault("corrections", [])
        CONVO_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_json(self):
        if MEMORY_FILE.exists():
            try:
                content = MEMORY_FILE.read_text(encoding="utf-8")
                saved = json.loads(content)
                for key, default in self.data.items():
                    if key in saved:
                        if isinstance(default, dict) and isinstance(saved[key], dict):
                            default.update(saved[key])
                            self.data[key] = default
                        else:
                            self.data[key] = saved[key]
            except Exception as e:
                try:
                    ts = int(time.time())
                    corrupted_path = MEMORY_FILE.with_suffix(f".corrupted_{ts}.json")
                    import shutil
                    shutil.copy2(MEMORY_FILE, corrupted_path)
                    print(f"[MEM ERROR] Failed to load JSON. Backed up corrupted file to: {corrupted_path}. Error: {e}")
                except Exception as backup_err:
                    print(f"[MEM ERROR] Failed to backup corrupted JSON: {backup_err}")

    def save(self):
        try:
            import tempfile
            from pathlib import Path
            dir_path = MEMORY_FILE.parent
            dir_path.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=str(dir_path), delete=False, suffix=".tmp", encoding="utf-8") as temp_file:
                json.dump(self.data, temp_file, indent=2, ensure_ascii=False)
                temp_file_path = temp_file.name
            
            import os
            os.replace(temp_file_path, str(MEMORY_FILE))
        except Exception as e:
            print("[MEM] Save failed: " + str(e))

    def add_fact(self, fact):
        fact = fact.strip()
        if not fact: return
        
        # ── Intelligence Filter: reject low-value content ──
        if not should_store(fact):
            print(f"[MEM] Filtered (low-value): {fact[:60]}...")
            return
        
        # ── Structured metadata ──
        classification = classify_memory(fact)
        metadata = {
            "time": datetime.datetime.now().isoformat(),
            "type": classification["type"],
            "importance": str(classification["importance"]),
            "tags": ",".join(classification["tags"]),
        }
        
        if self.facts_coll:
            try:
                doc_id = f"fact_{int(time.time()*1000)}"
                self.facts_coll.add(documents=[fact], metadatas=[metadata], ids=[doc_id])
                print(f"[MEM] Learned (Chroma|{classification['type']}|imp:{classification['importance']}): {fact}")
            except Exception as e:
                print(f"[MEM] Chroma save error: {e}")
        else:
            low = fact.lower()
            for existing in self.data["facts"]:
                if existing.lower() == low: return
                if self._same_topic(existing, fact):
                    self.data["facts"].remove(existing)
                    break
            self.data["facts"].append(fact)
            if len(self.data["facts"]) > 200: self.data["facts"].pop(0)
            self.save()
            print("[MEM] Learned: " + fact)

    def _same_topic(self, old, new):
        prefixes = [
            "my name is", "i am", "i'm", "i live", "i work",
            "i study", "my age", "i'm from", "call me",
        ]
        old_l, new_l = old.lower(), new.lower()
        for p in prefixes:
            if old_l.startswith(p) and new_l.startswith(p):
                return True
        return False

    def get_recent_facts(self, n=15):
        if self.facts_coll:
            try:
                res = self.facts_coll.get(limit=n)
                if res and res.get("documents"):
                    return res["documents"]
            except Exception:
                pass
        return self.data.get("facts", [])[-n:]

    def get_all_facts(self):
        if self.facts_coll:
            try:
                res = self.facts_coll.get()
                if res and res.get("documents"):
                    return [{"id": id_, "text": doc} for id_, doc in zip(res["ids"], res["documents"])]
            except Exception:
                pass
        return [{"id": f"fact_{i}", "text": f} for i, f in enumerate(self.data.get("facts", []))]

    def get_all_notes(self):
        return [{"id": n.get("id"), "text": n.get("text")} for n in self.data.get("notes", [])]

    def get_all_corrections(self):
        if self.corrections_coll:
            try:
                res = self.corrections_coll.get()
                if res and res.get("documents"):
                    return [{"id": id_, "text": doc} for id_, doc in zip(res["ids"], res["documents"])]
            except Exception:
                pass
        return [{"id": f"corr_{i}", "text": c.get("text") if isinstance(c, dict) else str(c)} for i, c in enumerate(self.data.get("corrections", []))]

    def get_all_conversations(self):
        if self.convo_coll:
            try:
                res = self.convo_coll.get()
                if res and res.get("documents"):
                    # Sort conversation entries by timestamp from IDs or metadata
                    zipped = list(zip(res["ids"], res["documents"], res["metadatas"]))
                    zipped.sort(key=lambda x: x[2].get("time", "") if x[2] else x[0], reverse=True)
                    return [{"id": item[0], "text": item[1]} for item in zipped]
            except Exception:
                pass
        return []

    def delete_fact_by_id(self, fact_id):
        fact_id_str = str(fact_id)
        if self.facts_coll:
            try:
                self.facts_coll.delete(ids=[fact_id_str])
            except Exception:
                pass
        # Sync json list by finding text match if key format was simple index
        if fact_id_str.startswith("fact_"):
            try:
                idx = int(fact_id_str.split("_")[1])
                if 0 <= idx < len(self.data.get("facts", [])):
                    self.data["facts"].pop(idx)
            except Exception:
                pass
        self.save()

    def delete_correction_by_id(self, corr_id):
        corr_id_str = str(corr_id)
        if self.corrections_coll:
            try:
                self.corrections_coll.delete(ids=[corr_id_str])
            except Exception:
                pass
        if corr_id_str.startswith("corr_"):
            try:
                idx = int(corr_id_str.split("_")[1])
                if 0 <= idx < len(self.data.get("corrections", [])):
                    self.data["corrections"].pop(idx)
            except Exception:
                pass
        self.save()

    def delete_convo_by_id(self, convo_id):
        convo_id_str = str(convo_id)
        if self.convo_coll:
            try:
                self.convo_coll.delete(ids=[convo_id_str])
            except Exception:
                pass
        self.save()

    def add_note(self, note):
        ts = datetime.datetime.now().isoformat()
        nid = int(time.time())
        entry = {"text": note, "time": ts, "id": nid}
        if self.notes_coll:
            try:
                self.notes_coll.add(documents=[note], metadatas=[{"time": ts, "id": nid}], ids=[f"note_{nid}"])
            except Exception as e:
                print(f"[MEM] Chroma note error: {e}")
        self.data.setdefault("notes", []).append(entry)
        self.save()
        return entry

    def get_notes(self):
        return self.data.get("notes", [])

    def delete_note(self, note_id):
        note_id_str = str(note_id)
        if self.notes_coll:
            try:
                self.notes_coll.delete(ids=[f"note_{note_id_str}"])
            except Exception:
                pass
        self.data["notes"] = [n for n in self.data.get("notes", []) if n.get("id") != note_id]
        self.save()

    def update_profile(self, key, value):
        if key in self.data["user_profile"]:
            if isinstance(self.data["user_profile"][key], list):
                if value not in self.data["user_profile"][key]:
                    self.data["user_profile"][key].append(value)
            else:
                self.data["user_profile"][key] = value
            self.save()
            print("[MEM] Profile updated: " + key + " = " + str(value))

    def add_preference(self, topic, sentiment):
        self.data["user_profile"]["preferences"][topic] = sentiment
        self.save()

    def track_topic(self, text):
        keywords = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        stopwords = {"what","that","this","with","from","have","will","your","about","would","could","should","there","their","been","were","being","does","doing","then","than","them","they","into","some","just","also","very","much","more","most","only","even","here","when","where","which","while","each","other","know","make","like","time","want","tell","open","please","thanks","thank","okay","edith","yeah","right"}
        for word in keywords:
            if word not in stopwords:
                self.data["topic_freq"][word] = self.data["topic_freq"].get(word, 0) + 1
        if len(self.data["topic_freq"]) > 150:
            sorted_topics = sorted(self.data["topic_freq"].items(), key=lambda x: x[1], reverse=True)
            self.data["topic_freq"] = dict(sorted_topics[:100])

    def get_top_topics(self, n=10):
        return sorted(self.data["topic_freq"].items(), key=lambda x: x[1], reverse=True)[:n]

    def log_exchange(self, user_text, ai_reply):
        self._session_log.append({
            "time": datetime.datetime.now().isoformat(),
            "user": user_text,
            "edith": ai_reply,
        })
        self.track_topic(user_text)
        
        # Store in ChromaDB vector space — but only if the exchange has value
        if self.convo_coll:
            doc_text = f"User said: {user_text}\nEDITH replied: {ai_reply}"
            
            # ── Intelligence Filter: skip trivial exchanges ──
            if not should_store(user_text):
                print(f"[MEM] Conversation filtered (low-value input): {user_text[:50]}")
            else:
                try:
                    classification = classify_memory(user_text)
                    metadata = {
                        "time": datetime.datetime.now().isoformat(),
                        "type": classification["type"],
                        "importance": str(classification["importance"]),
                        "tags": ",".join(classification["tags"]),
                    }
                    doc_id = f"convo_{int(time.time()*1000)}"
                    self.convo_coll.add(
                        documents=[doc_text],
                        metadatas=[metadata],
                        ids=[doc_id]
                    )
                    print(f"[MEM] Synced exchange (imp:{classification['importance']}): {user_text[:50]}")
                except Exception as e:
                    print(f"[MEM] Chroma conversation save error: {e}")
        
        # ── Periodic Compression ──
        self._exchange_count += 1
        if self._exchange_count >= self._compress_every:
            self._exchange_count = 0
            try:
                print("[MEM] Triggering periodic memory compression...")
                self.compress()
            except Exception as e:
                print(f"[MEM] Auto-compression error: {e}")

    def save_session_log(self):
        if not self._session_log: return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = CONVO_LOG_DIR / f"session_{ts}.json"
        try:
            log_file.write_text(json.dumps(self._session_log, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        summary = f"Session {ts}: {len(self._session_log)} exchanges"
        if self._session_log:
            topics = [ex["user"][:50] for ex in self._session_log[:3]]
            summary += " — Topics: " + "; ".join(topics)
        self.data.setdefault("conversations", []).append(summary)
        if len(self.data["conversations"]) > 30:
            self.data["conversations"].pop(0)
        self.save()

    def add_correction(self, correction):
        if self.corrections_coll:
            try:
                doc_id = f"corr_{int(time.time()*1000)}"
                self.corrections_coll.add(documents=[correction], metadatas=[{"time": datetime.datetime.now().isoformat()}], ids=[doc_id])
            except Exception:
                pass
        self.data.setdefault("corrections", []).append({
            "text": correction,
            "time": datetime.datetime.now().isoformat(),
        })
        if len(self.data["corrections"]) > 30:
            self.data["corrections"].pop(0)
        self.save()
        print("[MEM] Correction noted: " + correction)
        
    def get_corrections(self, n=5):
        if self.corrections_coll:
            try:
                res = self.corrections_coll.get(limit=n)
                if res and res.get("documents"):
                    return [{"text": d} for d in res["documents"]]
            except Exception:
                pass
        return self.data.get("corrections", [])[-n:]

    def start_session(self):
        self.data["last_seen"] = datetime.datetime.now().isoformat()
        self.data["session_count"] = self.data.get("session_count", 0) + 1
        self.save()

    def compress(self):
        """Run memory compression — dedup, cluster, and merge."""
        return _run_compression(self)

    def summary(self, current_query=None):
        lines = []
        now = datetime.datetime.now()
        lines.append(f"Current System Time: {now.strftime('%A, %Y-%m-%d %H:%M')}")
        
        if self.data.get("last_seen"): 
            lines.append("Last active: " + self.data["last_seen"][:16].replace("T", " at "))
        
        profile = self.data.get("user_profile", {})
        if profile.get("name"): lines.append("Subject Identity: " + profile["name"])
        if profile.get("occupation"): lines.append("Occupation: " + profile["occupation"])
        if profile.get("location"): lines.append("Current Base: " + profile["location"])
        
        # ── Smart Retrieval: ranked, deduplicated, importance-weighted ──
        smart_context_added = False
        if current_query and self.chroma_client:
            smart_ctx = smart_retrieve(current_query, self, n_results=5)
            if smart_ctx:
                lines.append("\n[RELEVANT NEURAL DATA]")
                lines.append(smart_ctx)
                smart_context_added = True

        # Fallback to raw JSON facts if smart retrieval returned nothing
        if not smart_context_added and self.data.get("facts"):
            lines.append("\n[RELEVANT NEURAL DATA]")
            for f in self.data["facts"][-10:]:
                lines.append("  - " + f)
        
        # Semantic Correction Retrieval (kept as-is — corrections are always valuable)
        corr_added = False
        if self.corrections_coll and current_query:
            try:
                res = self.corrections_coll.query(query_texts=[current_query], n_results=3)
                if res and res.get("documents") and res["documents"][0]:
                    lines.append("\n[USER PREFERENCE CORRECTIONS]")
                    for c in res["documents"][0]:
                        lines.append("  - " + c)
                    corr_added = True
            except Exception:
                pass
        if not corr_added and self.data.get("corrections"):
            lines.append("\n[USER PREFERENCE CORRECTIONS]")
            for c in self.data["corrections"][-5:]:
                val = c["text"] if isinstance(c, dict) else str(c)
                lines.append("  - " + val)

        # Explicit Profile Data
        if profile.get("interests") or profile.get("skills"):
            lines.append("\n[USER PROFILE]")
            if profile.get("interests"): lines.append("  Interests: " + ", ".join(profile["interests"][-5:]))
            if profile.get("skills"): lines.append("  Skills: " + ", ".join(profile["skills"][-5:]))
            if profile.get("preferences"):
                prefs = [f"{k} ({v})" for k, v in list(profile["preferences"].items())[-5:]]
                lines.append("  General Prefs: " + ", ".join(prefs))

        # Global Context
        top = self.get_top_topics(5)
        if top: lines.append("\n[FREQUENT TOPICS]: " + ", ".join(t[0] for t in top))

        # Adaptive Interaction Style
        style = self.data.get("interaction_style", {})
        if style:
            lines.append("\n[YOUR ADAPTIVE BEHAVIOR (ADJUST YOUR STYLE TO THIS)]")
            for k, v in style.items():
                if isinstance(v, bool):
                    status = "YES" if v else "NO"
                    lines.append(f"  - {k.replace('_', ' ').capitalize()}: {status}")
                else:
                    lines.append(f"  - {k.capitalize()}: {v}")

        if self.data.get("conversations"):
            lines.append("\n[RECENT SESSIONS]")
            for s in self.data["conversations"][-2:]:
                lines.append("  - " + s)

        if self.data.get("notes"):
            lines.append(f"\n[ACTIVE NOTES]: {len(self.data['notes'])} items pending.")

        return "\n".join(lines)
