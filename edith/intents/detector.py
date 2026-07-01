import re
import threading
from edith.core.state import state, state_lock
from edith.tools.system import open_app, close_tab, get_system_info, get_weather
from edith.tools.search import search_web, deep_search, open_website, _wikipedia_search, _ddg_news
from edith.tools.intel import get_briefing_data, generate_llm_context

# ── Agentic Intent Detection ─────────────────────────────────
_AGENTIC_PATTERNS = [
    # File creation/writing
    r"\b(?:create|make|write|generate|save|build)\b.{0,40}\b(?:file|script|code|program|document|txt|py|js|html|json|csv)\b",
    r"\b(?:create|make|build)\b.{0,30}\b(?:folder|directory)\b",
    # File deletion / moving
    r"\b(?:delete|remove|erase|wipe|clean\s+up)\b.{0,40}\b(?:file|folder|directory|temp|log)\b",
    r"\b(?:move|rename|copy)\b.{0,40}\b(?:file|folder|from|to)\b",
    # File reading
    r"\b(?:read|show|display|open|print|cat|get\s+contents?\s+of)\b.{0,40}\b(?:file|\.txt|\.log|\.py|\.json|\.csv)\b",
    # File finding
    r"\b(?:find|search\s+for|locate|look\s+for)\b.{0,40}\b(?:files?|named|called|with\s+extension)\b",
    r"\b(?:list|show)\b.{0,40}\b(?:files?|folders?|directory|contents?\s+of|desktop|downloads?|documents?)\b",
    # Shell / command execution — broad
    r"\b(?:run|execute|launch|start)\b.{0,40}\b(?:command|script|code|\.py|\.bat|\.ps1|python|node|pip|npm)\b",
    r"\b(?:run|execute)\b.{0,30}\b(?:ipconfig|ifconfig|ping|curl|wget|tracert|nslookup|netstat|tasklist|dir|ls)\b",
    r"\bipconfig\b|\bifconfig\b|\bping\b|\btracert\b|\bnslookup\b|\bnetstat\b|\btasklist\b",
    # Installation
    r"\b(?:install|uninstall|upgrade|pip\s+install|npm\s+install)\b",
    # Network info
    r"\b(?:ip\s+address|my\s+ip|local\s+ip|network\s+info|hostname|wifi\s+info)\b",
    # Process management
    r"\b(?:kill|stop|end|terminate|close)\b.{0,30}\b(?:process|task|program|application|app)\b",
    r"\b(?:what|which|list|show|get)\b.{0,30}\b(?:processes?|running\s+(?:apps?|programs?|tasks?))\b",
    r"\bprocesses?\s+(?:are\s+)?running\b",
    r"\btask\s+manager\b",
    # Screenshot / screen
    r"\b(?:take|capture|grab|snap)\b.{0,20}\b(?:screenshot|screen\s+capture|screengrab|snap)\b",
    r"\bscreenshot\b",
    # GUI control
    r"\b(?:click|double.?click)\b",
    r"\b(?:type|enter|input)\b.{0,30}\b(?:text|into|on\s+the)\b",
    r"\b(?:press|hit)\b.{0,20}\b(?:ctrl|alt|shift|win|enter|escape|tab|hotkey)\b",
    # Clipboard
    r"\b(?:clipboard|copy\s+to\s+clipboard|paste\s+from\s+clipboard)\b",
    # Multi-step compound
    r"\b(?:write|create).{0,30}(?:and|then).{0,30}(?:run|execute|test|launch)\b",
    r"\b(?:download|fetch|pull).{0,30}\b(?:from|url|link|http)\b",
    r"\b(?:zip|unzip|compress|extract)\b.{0,30}\b(?:file|folder|archive)\b",
    # Messaging / Social
    r"\b(?:send|write|type|post)\b.{0,40}\b(?:message|email|mail|tweet|whatsapp|discord|text)\b",
    r"\b(?:message|email|text)\b.{1,20}\b(?:saying|that|to)\b",
    # Generic Complex actions
    r"\b(?:open|launch).{1,20}\b(?:and|then).{1,30}\b(?:send|type|click|write)\b",
]

# Special marker returned from detect_and_act to signal agentic routing
AGENT_ROUTE = "__AGENT_ROUTE__"
VISION_ROUTE = "__VISION_ROUTE__"

def is_agentic_request(text: str) -> bool:
    """Return True if the user's request requires multi-step system execution."""
    low = text.lower().strip()
    if len(low) < 4:
        return False
    # Quick exclusion for simple greetings/intents
    simple = [
        "hello", "hi", "hey", "thanks", "thank you", "goodbye", "goodnight",
        "weather", "timer", "alarm", "note", "map", "news", "briefing",
        "kill mode", "standby", "sleep", "shut down", "open youtube",
    ]
    if low in simple or any(low == s for s in simple):
        return False
    for pat in _AGENTIC_PATTERNS:
        if re.search(pat, low):
            return True
    return False

def detect_and_act(text, memory, emit_funcs):
    low = text.lower()
    emit_kill_mode = emit_funcs.get("kill_mode")
    emit_close_map = emit_funcs.get("close_map")
    emit_map       = emit_funcs.get("map")
    emit_weather   = emit_funcs.get("weather")
    emit_note      = emit_funcs.get("note")
    emit_timer     = emit_funcs.get("timer")
    emit_alarm     = emit_funcs.get("alarm")
    emit_debug     = emit_funcs.get("debug")

    # INSTANT KILL
    if any(p in low for p in ["activate instant kill", "instant kill mode", "enable instant kill", "kill protocol", "activate kill mode", "turn on kill mode"]):
        state.kill_mode = True
        if emit_kill_mode: emit_kill_mode(True)
        return "Instant Kill Protocol activated."
    if any(p in low for p in ["deactivate instant kill", "disable instant kill", "normal mode", "deactivate kill mode", "de-activate kill mode", "kill mode off", "exit kill mode", "stop kill mode", "turn off kill mode"]):
        state.kill_mode = False
        if emit_kill_mode: emit_kill_mode(False)
        return "Instant Kill Protocol deactivated. Standard mode restored."

    # CLOSE TAB
    if any(p in low for p in ["close tab", "close this tab"]):
        return close_tab()

    # GO BACK
    if any(p in low for p in ["go back", "close map", "close the map", "back to main", "exit map", "hide map", "close briefing", "close news", "exit news", "exit briefing"]):
        if emit_close_map: emit_close_map()
        emit_close_world_briefing = emit_funcs.get("close_world_briefing")
        if emit_close_world_briefing: emit_close_world_briefing()
        return "Returning to main view."

    # VISION (Screen Context)
    if any(p in low for p in ["what am i looking at", "what is on my screen", "summarize this screen", "read my screen", "look at my screen", "what's on my screen"]):
        return VISION_ROUTE

    # MAP / LOCATE
    map_patterns = [
        r"(?:locate|find|show me|where is|map of|navigate to|directions to)\s+(.+)",
        r"(?:show|open)\s+(?:the\s+)?map\s+(?:of|for)\s+(.+)",
    ]
    for pat in map_patterns:
        m = re.search(pat, low)
        if m:
            place = m.group(1).strip()
            if emit_map: emit_map(place)
            return f"Locating {place} on the tactical grid."

    # WEATHER
    wx = re.search(r"weather(?:\s+in\s+(.+))?", low)
    if wx:
        city = (wx.group(1) or "").strip().rstrip("?.")
        def fetch_wx():
            res = get_weather(city)
            if res and emit_weather: emit_weather(res)
        threading.Thread(target=fetch_wx, daemon=True).start()
        return f"Fetching weather{' for ' + city if city else ''}..."

    # NOTE TAKING
    note_match = re.search(r"(?:note|remember|save|log)\s+(?:that\s+|this:\s*)?(.+)", low)
    if note_match:
        note_text = note_match.group(1).strip()
        entry = memory.add_note(note_text)
        if emit_note: emit_note("add", entry)
        return f"Noted: {note_text}"

    # TIMER
    timer_match = re.search(
        r"(?:set\s+)?timer\s+(?:for\s+)?(\d+)\s*(second|minute|hour|sec|min|hr)s?",
        low
    )
    if timer_match:
        amount = int(timer_match.group(1))
        unit   = timer_match.group(2)
        if unit in ("minute", "min"): secs = amount * 60
        elif unit in ("hour", "hr"): secs = amount * 3600
        else: secs = amount
        label = f"{amount} {unit} timer"
        if emit_timer: emit_timer("start", secs, label)
        return f"Timer set for {amount} {unit}{'s' if amount > 1 else ''}."

    # ALARM
    alarm_match = re.search(r"(?:set\s+)?alarm\s+(?:for\s+|at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", low)
    if alarm_match:
        h  = int(alarm_match.group(1))
        mn = int(alarm_match.group(2) or 0)
        ampm = alarm_match.group(3)
        if ampm == "pm" and h < 12: h += 12
        if ampm == "am" and h == 12: h = 0
        alarm_time = f"{h:02d}:{mn:02d}"
        if emit_alarm: emit_alarm({"time": alarm_time, "label": "E.D.I.T.H. Alarm"})
        return f"Alarm set for {alarm_time}."

    # SYSTEM INFO
    if any(p in low for p in ["system status", "cpu", "memory usage", "ram", "disk space", "system info"]):
        info = get_system_info()
        if info:
            return (f"CPU: {info['cpu']}% | RAM: {info['ram_used']}GB / {info['ram_total']}GB "
                    f"({info['ram_pct']}%) | Disk: {info['disk_pct']}%")
        return "System monitoring error."

    # NETWORK / IP INFO
    if any(p in low for p in ["my ip", "ip address", "network info", "network status", "pull up my ip"]):
        try:
            import socket
            import requests
            # Using a trick to get the actual active local IP instead of just 127.0.0.1
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            try:
                public_ip = requests.get("https://api.ipify.org", timeout=3).text
            except Exception:
                public_ip = "Unknown (offline)"
            return f"Your Local IP is {local_ip}, and your Public IP is {public_ip}."
        except Exception as e:
            return "Unable to fetch network configuration at this time."

    # NOTIFICATIONS
    if any(p in low for p in ["read notifications", "show notifications", "what are my notifications", "did i miss anything"]):
        with state_lock:
            if not state.recent_notifications:
                return "You have no new notifications."
            return "Here are your recent notifications: " + " \n".join(state.recent_notifications)

    # CLIPBOARD CONTEXT
    if any(p in low for p in ["what did i copy", "read my clipboard", "clipboard content"]):
        if state.clipboard_summary:
            return f"Based on what you recently copied: {state.clipboard_summary}"
        elif state.current_clipboard:
            clip = state.current_clipboard
            return f"Your clipboard contains: {clip[:200] + '...' if len(clip) > 200 else clip}"
        return "Your clipboard is currently empty."

    # MUSIC PLAYER
    music_match = re.search(r"^play\s+(?!youtube\b)(.+)", low)
    if music_match:
        query = music_match.group(1).strip()
        emit_music = emit_funcs.get("music")
        if emit_music:
            def fetch_music():
                import urllib.request
                import urllib.parse
                try:
                    html = urllib.request.urlopen("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query), timeout=5)
                    video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
                    if video_ids:
                        emit_music(video_ids[0], query)
                except Exception:
                    pass
            threading.Thread(target=fetch_music, daemon=True).start()
            return f"Playing {query}."
        return f"Playing {query}."

    # YOUTUBE
    yt = re.search(r"(?:open |search |play )?youtube(?:.+?for (.+)|(.+))?", low)
    if yt:
        query = (yt.group(1) or yt.group(2) or "").strip()
        if query:
            open_website("https://www.youtube.com/results?search_query=" + query.replace(" ", "+"))
            return "Opened YouTube and searched for: " + query
        open_website("https://youtube.com")
        return "Opened YouTube"

    # WEBSITE
    site = re.search(
        r"(?:open|go to|visit) (?:the )?(?:website |site )?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})", low
    )
    if site:
        url = site.group(1)
        open_website(url)
        return "Opened " + url

    # GOOGLE SEARCH
    google = re.search(r"(?:google|search for|search up|look up) (.+)", low)
    if google:
        q = google.group(1).strip()
        open_website("https://www.google.com/search?q=" + q.replace(" ", "+"))
        return "Searched Google for: " + q

    # APP OPEN
    app_match = re.search(r"open (?:the |my )?(.+?)(?:\s+app)?$", low)
    if app_match:
        a = app_match.group(1).strip()
        
        # If the app name is too long, it's likely a complex command (e.g. "open X and do Y"). Let the Brain handle it.
        if len(a.split()) <= 3 and not any(w in a.split() for w in ["and", "send", "tell", "write", "search"]):
            is_phone_cmd = (
                "on my phone" in a or 
                "on the phone" in a or 
                "on phone" in a or 
                a.startswith("phone ") or
                state.phone_mode
            )
            if is_phone_cmd:
                clean_app = re.sub(r"\s*on\s+(?:my\s+|the\s+)?phone", "", a).strip()
                if clean_app.startswith("phone "):
                    clean_app = clean_app[6:].strip() # Strip "phone " prefix
                
                emit_phone = emit_funcs.get("open_phone_app")
                if emit_phone: emit_phone(clean_app)
                return f"Opening {clean_app} on your device."
            elif a not in ["tab", "window", "browser", "website", "site", "map"]:
                return open_app(a)

    # WIKIPEDIA EXPLICIT
    wiki_match = re.search(r"(?:wikipedia|wiki)(?:\s+(?:on|about|for))?\s+(.+)", low)
    if wiki_match:
        q = wiki_match.group(1).strip()
        result = _wikipedia_search(q, sentences=8)
        return result if result else search_web(q)

    # WORLD BRIEFING / GENERAL NEWS
    broad_patterns = [
        r"^(?:what|whats|what's)\s+(?:is\s+)?happening(?:\s+around\s+the\s+world)?$",
        r"^happenings(?:\s+around\s+the\s+world)?$",
        r"^(?:show|open|play|get|give\s+me|tell\s+me)(?:\s+the)?\s+news$",
        r"^news$",
        r"^world\s+news$",
        r"^global\s+briefing$",
        r"^world\s+status$",
        r"^global\s+status$",
        r"^briefing$"
    ]
    is_broad = False
    for pat in broad_patterns:
        if re.search(pat, low.strip()):
            is_broad = True
            break
            
    if is_broad:
        emit_world_briefing = emit_funcs.get("world_briefing")
        if emit_world_briefing:
            data = get_briefing_data()
            emit_world_briefing(data)
            return (
                "The user is entering the World Briefing HUD. "
                "Here is the real-time data fetched for you:\n"
                f"{generate_llm_context(data)}\n"
                "Please act as E.D.I.T.H. greeting the user, confirming that the live tactical briefing feed is active, "
                "and summarizing what's happening (explain Nvidia stock, F1 standings, and top world news headlines in a concise, tactical, and informative briefing)."
            )

    # NEWS
    news_match = re.search(r"(?:news|latest|current events?)(?:\s+(?:about|on))?\s*(.*)", low)
    if news_match:
        q = (news_match.group(1) or text).strip()
        news = _ddg_news(q, max_results=5)
        if news:
            lines = [f"- [{n.get('date','')[:10]}] {n.get('title','')}: {n.get('body','')[:200]}" for n in news]
            return "[Latest News]\n" + "\n".join(lines)
        return search_web(q)

    # DEEP SEARCH explicit
    deep_match = re.search(r"(?:deep search|research|deep dive|find everything)(?:\s+(?:on|about|for))?\s+(.+)", low)
    if deep_match:
        q = deep_match.group(1).strip()
        return deep_search(q)

    # ── AGENTIC TASK ROUTING ─────────────────────────────────
    if is_agentic_request(text):
        emit_debug = emit_funcs.get("debug")
        if emit_debug:
            emit_debug("Agentic task detected — engaging Agent Engine...")
        return AGENT_ROUTE

    return ""
