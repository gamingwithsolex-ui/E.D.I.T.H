import sys
import re
import threading
import httpx
from openai import OpenAI
from edith.config import (
    MAIN_MODEL, GEMINI_API_KEY,
    DEEPSEEK_API_KEY, STRATEGIC_MODEL,
    OPENAI_API_KEY, OLLAMA_ENDPOINT, LOCAL_MODEL_NAME
)
from edith.core.state import state, set_state
from edith.core.personality import build_prompt, build_kill_prompt, build_support_prompt
from edith.memory import auto_remember
import json
import time

# ── Conversation History (Main Brain owns this) ──────────────────────────
CONVO_HISTORY = []
GEMINI_FALLBACK_CHAIN = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-3.5-flash"]
CURRENT_GEMINI_INDEX = 0

# ── Model Aliases ────────────────────────────────────────────────────────
MAIN_FALLBACK_CHAIN = ["llama-3.3-70b-versatile"]
MODEL_SUPPORT = STRATEGIC_MODEL    # DeepSeek V4 Pro — Support Engine

# ── Confidence Gate Config ───────────────────────────────────────────────
CONFIDENCE_THRESHOLD = 0.6   # Below this → DeepSeek enriches the answer

# ── Clients ──────────────────────────────────────────────────────────────
client_main    = None   # Gemini (Primary LLM)
client_vision  = None   # Gemini (Vision API)
client_support = None   # DeepSeek V4 Pro
client_local = None     # Local Ollama Backend
client_openrouter = None # OpenRouter (Fallback API)

brain_lock = threading.Lock()

def ensure_clients():
    global client_main, client_vision, client_support, client_openrouter, client_local
    
    # Main Brain (Gemini) — REQUIRED
    if not client_main and GEMINI_API_KEY:
        try:
            client_main = OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=GEMINI_API_KEY,
                http_client=httpx.Client(trust_env=False),
                timeout=15,
                max_retries=0
            )
            print("[BRAIN] * Main Brain (Gemini Core) Online — Final Authority active.")
        except Exception as e:
            print(f"[BRAIN] Main Brain Error: {e}")

    # Vision Engine (Gemini)
    if not client_vision and GEMINI_API_KEY:
        try:
            client_vision = OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=GEMINI_API_KEY,
                http_client=httpx.Client(trust_env=False),
                timeout=15,
                max_retries=0
            )
            print("[BRAIN] Vision Engine (Gemini) Online — Standby for visual tasks.")
        except Exception as e:
            print(f"[BRAIN] Vision Engine Error: {e}")

    # Support Engine (DeepSeek V4 Pro) — OPTIONAL
    if not client_support and DEEPSEEK_API_KEY:
        try:
            client_support = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=DEEPSEEK_API_KEY,
                http_client=httpx.Client(trust_env=False),
                timeout=15,
                max_retries=0
            )
            print("[BRAIN] Support Engine (DeepSeek V4 Pro) Online — Standby for Main Brain requests.")
        except Exception as e:
            print(f"[BRAIN] Support Engine Error: {e}")

    # Local Backend Client (Ollama) - Zero API Limits
    if not client_local:
        import os
        import urllib.request
        import time
        import subprocess
        
        # Auto-start Ollama if it's not running
        if "localhost" in OLLAMA_ENDPOINT or "127.0.0.1" in OLLAMA_ENDPOINT:
            try:
                urllib.request.urlopen(OLLAMA_ENDPOINT.replace("/v1", ""), timeout=0.5)
            except Exception:
                print("[BRAIN] Ollama not detected. Attempting to start 'ollama serve' in background...")
                try:
                    creationflags = 0x08000000 if os.name == 'nt' else 0
                    import atexit
                    proc = subprocess.Popen(
                        ["ollama", "serve"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=creationflags
                    )
                    atexit.register(proc.kill)
                    time.sleep(2.0) # Give it a moment to boot
                except Exception as boot_err:
                    print(f"[BRAIN] Failed to auto-start Ollama: {boot_err}")

        try:
            client_local = OpenAI(
                base_url=OLLAMA_ENDPOINT,
                api_key="ollama", # Required by OpenAI client, but ignored by Ollama
                http_client=httpx.Client(trust_env=False), # Direct localhost connection
                timeout=30,
                max_retries=0
            )
            print("[BRAIN] Local Backend (Ollama) Online — Gatekeeper engine ready.")
        except Exception as e:
            print(f"[BRAIN] Local Backend Error: {e}")

    # OpenRouter API Client — OPTIONAL Fallback
    if not client_openrouter and OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-or-v1"):
        try:
            client_openrouter = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENAI_API_KEY,
                http_client=httpx.Client(trust_env=False),
                timeout=15,
                max_retries=0
            )
            print("[BRAIN] OpenRouter API Client Online — High-reliability fallback ready.")
        except Exception as e:
            print(f"[BRAIN] OpenRouter API Client Error: {e}")


# ── Confidence Parsing ────────────────────────────────────────────────────
_CONFIDENCE_PATTERN = re.compile(r"\[CONFIDENCE:\s*([\d.]+)\]", re.IGNORECASE)

def _parse_confidence(raw_reply):
    """
    Extract the confidence score from Gemini's reply.
    Gemini is instructed to append [CONFIDENCE: 0.XX] to every response.
    Returns (clean_reply, confidence_float).
    """
    match = _CONFIDENCE_PATTERN.search(raw_reply)
    if match:
        score = float(match.group(1))
        score = max(0.0, min(1.0, score))  # clamp
        clean = _CONFIDENCE_PATTERN.sub("", raw_reply).strip()
        return clean, score
    # No tag found → assume moderate confidence (default pass-through)
    return raw_reply.strip(), 0.75


def _parse_map_tags(raw_reply, emit_debug=None):
    import re
    try:
        from edith.interfaces.web.server import emit_map, emit_close_map, socketio
    except ImportError:
        return raw_reply
        
    clean_reply = raw_reply
    
    # 1. Search tag: [MAP_SEARCH: place name]
    search_match = re.search(r"\[MAP_SEARCH:\s*(.+?)\]", clean_reply, re.IGNORECASE)
    if search_match:
        place = search_match.group(1).strip()
        emit_map(place)
        if emit_debug:
            emit_debug(f"Map Target Locked: {place}")
            
    # 2. Zoom tag: [MAP_ZOOM: in] or [MAP_ZOOM: out]
    zoom_match = re.search(r"\[MAP_ZOOM:\s*(in|out)\]", clean_reply, re.IGNORECASE)
    if zoom_match:
        direction = zoom_match.group(1).lower()
        socketio.emit("map_cmd", {"action": f"zoom_{direction}"})
        if emit_debug:
            emit_debug(f"Map Command: ZOOM {direction.upper()}")
            
    # 2.5. Pan tag: [MAP_PAN: up|down|left|right]
    pan_match = re.search(r"\[MAP_PAN:\s*(up|down|left|right)\]", clean_reply, re.IGNORECASE)
    if pan_match:
        direction = pan_match.group(1).lower()
        socketio.emit("map_cmd", {"action": f"pan_{direction}"})
        if emit_debug:
            emit_debug(f"Map Command: PAN {direction.upper()}")
            
    # 3. Close tag: [MAP_CLOSE]
    if "[MAP_CLOSE]" in clean_reply.upper():
        emit_close_map()
        if emit_debug:
            emit_debug("Map Command: CLOSE")
            
    # Strip all [MAP_xxx] tags
    clean_reply = re.sub(r"\[MAP_.*?\]", "", clean_reply, flags=re.IGNORECASE).strip()
    return clean_reply



def _fetch_confidence_assist(user_input, gemini_reply, confidence, memory):
    """
    DeepSeek V4 Pro assists when Gemini's confidence is LOW.
    It receives Gemini's draft + the original query and produces
    a refined, enriched answer for the Main Brain to use.
    """
    try:
        support_prompt = build_support_prompt()
        support_prompt += (
            "\n\nCONFIDENCE ASSIST MODE:\n"
            "The Main Brain (Gemini) answered the user but flagged LOW CONFIDENCE "
            f"(score: {confidence:.2f}). Your job is to ENRICH and IMPROVE the "
            "Main Brain's draft. Fix inaccuracies, add missing detail, and sharpen "
            "the response. Keep the Main Brain's personality and tone intact.\n"
            "Do NOT add your own personality. Output a polished final answer.\n"
        )
        mem_summary = memory.summary(user_input) if memory else ""
        if mem_summary:
            support_prompt += f"\nMEMORY CONTEXT:\n{mem_summary}\n"

        support_msgs = [
            {"role": "system", "content": support_prompt},
            {"role": "user", "content": (
                f"User's original request: {user_input}\n\n"
                f"Gemini's low-confidence draft (score {confidence:.2f}):\n"
                f"{gemini_reply}\n\n"
                f"Produce an improved, accurate, and complete final answer."
            )}
        ]
        resp = client_support.chat.completions.create(
            model=MODEL_SUPPORT,
            messages=support_msgs,
            max_tokens=800
        )
        content = resp.choices[0].message.content
        if not content:
            content = getattr(resp.choices[0].message, "reasoning_content", None)
        return (content or "").strip()
    except Exception as e:
        print(f"[BRAIN] Confidence Assist Failure: {e}")
        return ""


def _fetch_support_fallback(user_input, memory, is_low_output=False):
    """
    Support Engine (DeepSeek V4 Pro) — acts as the direct fallback if Gemini fails
    or if Gemini's output was critically low.
    """
    try:
        mem_summary = memory.summary(user_input) if memory else ""
        support_prompt = build_support_prompt() + "\n\nCRITICAL OVERRIDE: The Main Brain has failed. You are now the FALLBACK answering directly. Be concise and helpful.\n\nMEMORY:\n" + mem_summary
        
        reason = "The Main Brain provided an inadequate response." if is_low_output else "The Main Brain experienced a total failure."
        
        support_msgs = [
            {"role": "system", "content": support_prompt},
            {"role": "user", "content": (
                f"{reason}\n"
                f"User said: {user_input}\n\n"
                f"Provide the final direct answer to the user now."
            )}
        ]
        resp = client_support.chat.completions.create(
            model=MODEL_SUPPORT,
            messages=support_msgs,
            max_tokens=600
        )
        content = resp.choices[0].message.content
        if not content:
            content = getattr(resp.choices[0].message, "reasoning_content", None)
        return (content or "").strip()
    except Exception as e:
        print(f"[BRAIN] Support Engine Fallback Failure: {e}")
        return ""


def should_search_web(user_input):
    low = user_input.lower().strip()
    
    if len(low) < 4:
        return False
        
    import re
    ignore_patterns = [
        r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bhow are you\b", r"\bwhat is your name\b",
        r"\bwho are you\b", r"\bthank you\b", r"\bthanks\b", r"\bgo to sleep\b", r"\bshutdown\b",
        r"\bexit\b", r"\bquit\b", r"\btimer\b", r"\balarm\b", r"\bnote\b", r"\bremember\b",
        r"\bweather\b", r"\bmap of\b", r"\blocate\b", r"\bopen the app\b", r"\bopen chrome\b",
        r"\bopen notepad\b", r"\bclose tab\b", r"\btell me a joke\b", r"\bsing a song\b",
        r"\bstandby\b", r"\bgo dark\b", r"\bpower down\b", r"\bengage\b", r"\bdisengage\b",
        r"\bkill mode\b"
    ]
    if any(re.search(pat, low) for pat in ignore_patterns):
        return False
        
    search_keywords = [
        "who is", "what is", "where is", "when did", "how many", "why did", 
        "current", "latest", "recent", "today", "yesterday", "news", "price of",
        "stock", "versus", "vs", "winner", "won", "score", "match", "game", 
        "result", "happen", "released", "launch", "announcement", "ceo", "president",
        "leader", "champion", "update", "population", "capital of", 
        "who won", "how did", "status of", "internet", "web search", "search up",
        "google", "lookup", "look up", "find info on", "tell me about"
    ]
    if any(kw in low for kw in search_keywords):
        return True
        
    question_starters = ["who", "what", "where", "when", "why", "how", "is", "are", "was", "were", "do", "does", "did", "can", "could", "will", "would", "has", "have", "had"]
    words = low.split()
    if words and (words[0] in question_starters or low.endswith("?")):
        return True
        
    return False


def clean_search_query(text):
    low = text.lower().strip()
    from edith.config import WAKE_WORDS
    for w in sorted(WAKE_WORDS, key=len, reverse=True):
        if low.startswith(w):
            low = low[len(w):].strip()
        low = low.replace(w, "").strip()
    
    fillers = [
        "can you tell me", "do you know", "please search for", "search for", 
        "look up", "tell me about", "what is the", "who is the", "tell me", "please",
        "what is", "who is", "where is", "when was", "search up", "google", "look up",
        "find info on", "find information about", "find out"
    ]
    for f in sorted(fillers, key=len, reverse=True):
        if low.startswith(f):
            low = low[len(f):].strip()
            
    low = low.rstrip("?.!")
    return low.strip() if low.strip() else text


def _describe_image_with_gemini(image_path):
    """
    Use Gemini (client_main) to generate a detailed description of the image at image_path.
    """
    ensure_clients()
    if not client_main:
        raise Exception("Gemini client is offline; cannot analyze image.")
        
    import base64
    import mimetypes
    
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/jpeg"
        
    with open(image_path, "rb") as f:
        img_data = f.read()
    img_base64 = base64.b64encode(img_data).decode("utf-8")
    
    system_prompt = (
        "You are E.D.I.T.H.'s Vision Processing Unit. "
        "Analyze this image and describe it in meticulous detail. "
        "List all visible elements, text, color schemes, data, layout, code snippets, "
        "or anything else present. Be objective, precise, and highly detailed, "
        "so another language model can understand and reason about the image."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": "Please analyze this image in detail."},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{img_base64}"
                }
            }
        ]}
    ]
    
    global CURRENT_GEMINI_INDEX
    with brain_lock:
        if CURRENT_GEMINI_INDEX >= len(GEMINI_FALLBACK_CHAIN):
            CURRENT_GEMINI_INDEX = 0
        
    raw_reply = None
    
    while CURRENT_GEMINI_INDEX < len(GEMINI_FALLBACK_CHAIN):
        current_model = GEMINI_FALLBACK_CHAIN[CURRENT_GEMINI_INDEX]
        try:
            response = client_vision.chat.completions.create(
                model=current_model,
                messages=messages,
                max_tokens=1000
            )
            content = response.choices[0].message.content
            if not content:
                content = getattr(response.choices[0].message, "reasoning_content", None)
            if content:
                raw_reply = content.strip()
                CURRENT_GEMINI_INDEX = 0
                break
            else:
                CURRENT_GEMINI_INDEX += 1
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "404" in err_str:
                print(f"[VISION] Model issue ({current_model}). Falling back...")
                with brain_lock:
                    CURRENT_GEMINI_INDEX += 1
            else:
                raise e
                
    if not raw_reply:
        raise Exception("All Gemini models exhausted their quota or failed during vision analysis.")
        
    return raw_reply


def _read_text_file(file_path):
    """
    Read content of a text file, handle different encodings safely.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"[Error reading file: {e}]"


def ask_edith(user_input, memory, extra_context="", emit_debug=None, file_path=None):
    """
    Confidence-Gated Routing Logic:
    1. Always send to Gemini FIRST (Main Brain), EXCEPT when a file/image is uploaded from mobile.
    2. When a file is uploaded, we pre-process it (describe image using Gemini Vision, or read text content).
       Then, we route the compiled context + request directly to DeepSeek v4 (MODEL_SUPPORT).
    3. Standard text queries use the Confidence-Gated Gemini first, DeepSeek fallback pipeline.
    """
    ensure_clients()
    import os

    file_context = ""
    if file_path and os.path.exists(file_path):
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic", ".heif"]:
            if emit_debug:
                emit_debug(f"Processing image upload '{filename}' with Gemini Vision...")
            try:
                img_desc = _describe_image_with_gemini(file_path)
                file_context = f"[ATTACHED IMAGE: {filename}]\nGemini Vision Analysis:\n{img_desc}\n"
                if emit_debug:
                    emit_debug("Image analysis completed successfully.")
            except Exception as ve:
                file_context = f"[ATTACHED IMAGE: {filename} (Error analyzing image: {ve})]\n"
                if emit_debug:
                    emit_debug(f"Image analysis failed: {ve}")
        else:
            if emit_debug:
                emit_debug(f"Reading file attachment '{filename}'...")
            content = _read_text_file(file_path)
            if len(content) > 100000:
                content = content[:100000] + "\n\n... [CONTENT TRUNCATED DUE TO SIZE] ..."
            file_context = f"[ATTACHED FILE: {filename}]\nContent:\n{content}\n"
            if emit_debug:
                emit_debug("File loaded successfully.")
                
    if file_context:
        extra_context = file_context + "\n" + extra_context


    # Route directly to DeepSeek V4 Pro if file is uploaded and support client is online
    if file_path and client_support:
        if emit_debug:
            emit_debug("Routing file query to DeepSeek v4...")
            
        prompt_fn = build_kill_prompt if state.kill_mode else build_prompt
        sys_instruction = prompt_fn(memory.summary(user_input) if memory else "")
        sys_instruction += "\n\n[SYSTEM DIRECTION] You are answering directly as E.D.I.T.H. A file has been uploaded from the user's phone. Use the attached file content / image analysis to fulfill the request. Be concise, sharp, and helpful."
        
        msg = user_input
        if file_context:
            msg = f"{file_context}\n\nUser request: {user_input}"
        if extra_context:
            msg += f"\n\n[SYSTEM CONTEXT: {extra_context}]"
            
        with brain_lock:
            CONVO_HISTORY.append({"role": "user", "content": msg})
            while len(CONVO_HISTORY) > 20:
                CONVO_HISTORY.pop(0)
            
            messages = [{"role": "system", "content": sys_instruction}]
            messages.extend(CONVO_HISTORY)
        
        set_state("thinking")
        try:
            resp = client_support.chat.completions.create(
                model=MODEL_SUPPORT,
                messages=messages,
                max_tokens=1500,
                timeout=15.0
            )
            content = resp.choices[0].message.content
            if not content:
                content = getattr(resp.choices[0].message, "reasoning_content", "")
            reply = (content or "").strip()
            
            # Clean reply tags if any
            reply, _ = _parse_confidence(reply)
            reply = _parse_map_tags(reply, emit_debug)
            
            with brain_lock:
                CONVO_HISTORY.append({"role": "assistant", "content": reply})
            if memory:
                auto_remember(user_input, memory, reply)
                memory.log_exchange(user_input, reply)
            return reply
        except Exception as d_err:
            print(f"[ERROR] Direct DeepSeek call failed on file query: {d_err}")
            if emit_debug:
                emit_debug("DeepSeek failed. Falling back to Gemini Core...")


    # ── 0. Real-time Search Lookup ────────────────────────────────────
    if not extra_context and should_search_web(user_input):
        cleaned_q = clean_search_query(user_input)
        if emit_debug:
            emit_debug(f"Factual request detected. Checking secure external feeds for: '{cleaned_q}'...")
        try:
            from edith.tools.search import search_web
            search_results = search_web(cleaned_q)
            if search_results and "No results found" not in search_results:
                extra_context = f"[REAL-TIME WEB DATA for '{cleaned_q}']:\n{search_results}"
                if emit_debug:
                    emit_debug("Live web data successfully synchronized.")
            else:
                if emit_debug:
                    emit_debug("No significant search results returned.")
        except Exception as e:
            print(f"[BRAIN] Real-time Search Error: {e}")

    # ── 1. Route to Main Brain (Gemini) ────────────────────────────────
    msg = user_input
    if extra_context:
        msg += f"\n\n[SYSTEM CONTEXT: {extra_context}]"

    with brain_lock:
        CONVO_HISTORY.append({"role": "user", "content": msg})
        while len(CONVO_HISTORY) > 20:
            CONVO_HISTORY.pop(0)
        messages_to_send = list(CONVO_HISTORY)

    prompt_fn = build_kill_prompt if state.kill_mode else build_prompt
    sys_instruction = prompt_fn(memory.summary(user_input) if memory else "")

    # Inject confidence scoring directive into system prompt
    sys_instruction += (
        "\n\n═══ CONFIDENCE SELF-ASSESSMENT (MANDATORY) ═══\n"
        "At the VERY END of EVERY response, append a confidence tag on its own line:\n"
        "  [CONFIDENCE: X.XX]\n"
        "where X.XX is your honest self-assessed confidence from 0.00 to 1.00.\n\n"
        "SCORING GUIDE:\n"
        "  0.90–1.00 → You are certain. Factual, well-known, or within your training.\n"
        "  0.70–0.89 → Confident but some details may need verification.\n"
        "  0.50–0.69 → Uncertain. You're guessing or the topic is outside your knowledge.\n"
        "  0.00–0.49 → Very unsure. Speculative or you lack the data to answer well.\n\n"
        "BE HONEST. Under-confidence is better than over-confidence.\n"
        "The user will NEVER see this tag — it is parsed and stripped by the system.\n"
    )

    set_state("thinking")
    
    try:
        messages = [{"role": "system", "content": sys_instruction}]
        messages.extend(messages_to_send)
        
        raw_reply = None
        try:
            client = client_main
            kwargs = {
                "model": MAIN_MODEL,
                "messages": messages,
                "temperature": 0.85,
                "max_tokens": 1500,
                "stream": False
            }
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if not content:
                content = getattr(response.choices[0].message, "reasoning_content", None)
            if content:
                raw_reply = content.strip()
                set_state("active_model", MAIN_MODEL)
        except Exception as e:
            print(f"[BRAIN] Main Model issue: {e}")
            err_str = str(e).lower()
            if "timeout" in err_str or "connect" in err_str:
                set_state("network_timed_out", True)
                
            if client_local:
                print(f"[BRAIN] Falling back to Offline Local AI ({LOCAL_MODEL_NAME})...")
                try:
                    kwargs["model"] = LOCAL_MODEL_NAME
                    response = client_local.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content
                    if not content:
                        content = getattr(response.choices[0].message, "reasoning_content", None)
                    if content:
                        raw_reply = content.strip()
                        set_state("active_model", LOCAL_MODEL_NAME)
                except Exception as ex:
                    print(f"[BRAIN] Local AI fallback also failed: {ex}")
        
        if not raw_reply:
            raise Exception("Main model and offline fallback both failed.")
        
        # ── 2. Parse Confidence Score ──────────────────────────────────
        reply, confidence = _parse_confidence(raw_reply)
        
        if emit_debug:
            emit_debug(f"Main Brain confidence: {confidence:.2f}")
        print(f"[BRAIN] Confidence Score: {confidence:.2f} (threshold: {CONFIDENCE_THRESHOLD})")

        # ── 3. CONFIDENCE GATE ─────────────────────────────────────────
        if confidence < CONFIDENCE_THRESHOLD and client_support:
            # LOW CONFIDENCE → DeepSeek V4 Pro assists
            if emit_debug:
                emit_debug(f"Low confidence ({confidence:.2f}). Routing to Support Engine for enrichment...")
            
            assist_holder = {}
            def _run_assist():
                assist_holder["result"] = _fetch_confidence_assist(
                    user_input, reply, confidence, memory
                )
            t = threading.Thread(target=_run_assist, daemon=True)
            t.start()
            t.join(timeout=10)
            
            enriched = assist_holder.get("result", "")
            if enriched:
                reply = enriched
                if emit_debug:
                    emit_debug("Support Engine enrichment applied. Final answer upgraded.")
            else:
                if emit_debug:
                    emit_debug("Support Engine enrichment failed. Using Main Brain's original answer.")
        else:
            # HIGH CONFIDENCE → direct answer
            if emit_debug and confidence >= CONFIDENCE_THRESHOLD:
                emit_debug(f"High confidence ({confidence:.2f}). Direct answer — no assist needed.")

        reply = _parse_map_tags(reply, emit_debug)
        with brain_lock:
            CONVO_HISTORY.append({"role": "assistant", "content": reply})
        if memory:
            auto_remember(user_input, memory, reply)
            memory.log_exchange(user_input, reply)
        return reply

    except Exception as e:
        err = str(e)
        print("[ERROR] Main Brain Error: " + err)
        
        # ── 4. Fallback if Gemini Fails (Exception) ─────────────────────
        if getattr(state, "network_timed_out", False):
            print("[BRAIN] Skipping cloud fallbacks because network previously timed out.")
            return "I'm sorry, my neural nets are currently offline and the local backend failed. Please check my diagnostic logs."
            
        # Try OpenRouter first (high reliability)
        if client_openrouter:
            if emit_debug: emit_debug("Main Brain failed/Quota exceeded. OpenRouter taking command...")
            messages_fallback = [{"role": "system", "content": sys_instruction + "\n\n[SYSTEM OVERRIDE] Gemini is offline. YOU are now the Main Brain acting as E.D.I.T.H."}]
            with brain_lock:
                messages_fallback.extend(list(CONVO_HISTORY))
            for model in ["google/gemini-2.5-flash", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"]:
                try:
                    resp = client_openrouter.chat.completions.create(
                        model=model,
                        messages=messages_fallback,
                        max_tokens=1500
                    )
                    content = resp.choices[0].message.content
                    if not content:
                        content = getattr(resp.choices[0].message, "reasoning_content", "") or ""
                    reply = content.strip()
                    if reply:
                        reply, _ = _parse_confidence(reply)
                        reply = _parse_map_tags(reply, emit_debug)
                        with brain_lock:
                            CONVO_HISTORY.append({"role": "assistant", "content": reply})
                        if memory:
                            auto_remember(user_input, memory, reply)
                            memory.log_exchange(user_input, reply)
                        set_state("active_model", model)
                        return reply
                except Exception as or_err:
                    print(f"[BRAIN] OpenRouter fallback model '{model}' failed: {or_err}")
                    continue

        # Try Nvidia DeepSeek fallback second
        if client_support:
            if emit_debug: emit_debug("Main Brain failed/Quota exceeded. DeepSeek V4 Pro taking command...")
            
            # Rebuild prompt so DeepSeek knows it's the main brain now
            messages_fallback = [{"role": "system", "content": sys_instruction + "\n\n[SYSTEM OVERRIDE] Gemini is offline. YOU are now the Main Brain acting as E.D.I.T.H."}]
            with brain_lock:
                messages_fallback.extend(list(CONVO_HISTORY))
            
            try:
                resp = client_support.chat.completions.create(
                    model=MODEL_SUPPORT,
                    messages=messages_fallback,
                    max_tokens=1500
                )
                content = resp.choices[0].message.content
                if not content:
                    content = getattr(resp.choices[0].message, "reasoning_content", "")
                raw_reply = (content or "").strip()
                reply, _ = _parse_confidence(raw_reply)
                
                reply = _parse_map_tags(reply, emit_debug)
                with brain_lock:
                    CONVO_HISTORY.append({"role": "assistant", "content": reply})
                if memory:
                    auto_remember(user_input, memory, reply)
                    memory.log_exchange(user_input, reply)
                set_state("active_model", MODEL_SUPPORT)
                return reply
            except Exception as d_err:
                print(f"[ERROR] DeepSeek Fallback Error: {d_err}")
                
        if emit_debug: emit_debug("Critical Failure: Both Brains offline.")
        set_state("active_model", "OFFLINE")
        return "My apologies — the Main Brain hit a quota limit, and all fallbacks are currently offline. Try again shortly?"

def evaluate_telemetry(telemetry_event, emit_debug=None):
    """
    Evaluates incoming phone telemetry using Groq API.
    Enforces JSON structure for fast, strict execution without conversational filler.
    Handles rate limit 429 errors with exponential backoff.
    """
    ensure_clients()
    if not client_local:
        return
        
    from edith.core.state import state, state_lock
    
    # Intercept dict-based event objects
    if isinstance(telemetry_event, dict):
        event_type = telemetry_event.get("type")
        if event_type == "clipboard_summarize":
            content = telemetry_event.get("content", "")
            try:
                resp = client_local.chat.completions.create(
                    model=LOCAL_MODEL_NAME,
                    messages=[{"role": "user", "content": f"Summarize this text concisely in 1-2 sentences. No conversational filler, just the summary:\n\n{content}"}],
                    max_tokens=200
                )
                summary = resp.choices[0].message.content.strip()
                with state_lock:
                    state.clipboard_summary = summary
                if emit_debug: emit_debug("Clipboard summarization completed silently.")
            except Exception as e:
                print(f"[BRAIN] Clipboard summarize error: {e}")
            return None
            
        elif event_type == "morning_briefing":
            try:
                from edith.tools.system import get_weather
                wx = get_weather("local") or {}
                desc = wx.get("description", "unknown")
                temp = wx.get("temp", "unknown")
                batt = state.device_state.get('battery_level', 100)
                text = f"Good morning, Sir. The weather is {desc} at {temp}. Your phone is at {batt} percent battery. I am online and ready for your commands."
                return {"action": "speak", "data": {"text": text}}
            except Exception as e:
                print(f"[BRAIN] Morning briefing error: {e}")
                return {"action": "speak", "data": {"text": "Good morning, Sir. Systems are online."}}
                
        elif event_type == "notification":
            telemetry_event = telemetry_event.get("content", "")
    
    with state_lock:
        telemetry_context = (
            f"Incoming Telemetry Event:\n{telemetry_event}\n\n"
            f"Foreground App: {state.foreground_app}\n"
            f"Device State: {state.device_state}\n"
        )
        
    system_prompt = (
        "You are E.D.I.T.H., a tactical assistant predictive gatekeeper. You are monitoring the user's incoming telemetry.\n"
        "Evaluate the following telemetry data to determine contextual importance.\n"
        "1. Standard Notifications (app updates, promotional emails, group chats, background syncs): You must execute a silence-by-default return. Output exactly: {\"action\": \"idle_pulse\"}\n"
        "2. High-Priority Alerts (direct messages from real people on apps like Instagram/WhatsApp, text messages, critical system errors, security alerts): You must alert the user. Output a structured payload: {\"action\": \"speak\", \"data\": {\"text\": \"[Concise summary of the message/alert, do NOT read raw headers]\"}}\n"
        "Possible actions: 'idle_pulse', 'speak', 'execute_intent', 'inject_ui_action', 'run_shell_command'.\n"
        "DO NOT output any conversational text. ONLY output the JSON object."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": telemetry_context}
    ]
    
    max_retries = 3
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            resp = client_local.chat.completions.create(
                model=LOCAL_MODEL_NAME,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=300
            )
            
            content = resp.choices[0].message.content
            if content:
                try:
                    result = json.loads(content)
                    if isinstance(result, dict):
                        action = result.get("action")
                        if action and action != "none":
                            if emit_debug: emit_debug(f"Telemetry execution triggered: {action}")
                            return result
                except json.JSONDecodeError:
                    if emit_debug: emit_debug("Error decoding telemetry JSON payload.")
            return None
            
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                delay = base_delay * (2 ** attempt)
                if emit_debug: emit_debug(f"Local Model Rate Limit (429). Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"[BRAIN] Telemetry evaluation error: {e}")
                return None
    return None
