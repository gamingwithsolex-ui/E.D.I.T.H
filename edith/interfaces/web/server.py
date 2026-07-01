import sys
import os
import threading
import logging
import warnings
import urllib.request
import urllib.parse
import json
from flask import Flask, render_template, Response
from flask_socketio import SocketIO
from edith.config import UI_PORT, SESSION_DIR

# Suppress ALL Werkzeug output to stderr (PowerShell kills processes on stderr)
# logging.getLogger("werkzeug").setLevel(logging.ERROR)
# warnings.filterwarnings("ignore", message=".*Werkzeug.*production.*")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "edith_stark_2024"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", logger=True, engineio_logger=True, max_http_buffer_size=50000000)

# --- UTILITIES ---
def fetch_direct(url, headers=None):
    if headers is None:
        headers = {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = "EdithTacticalHUD/1.0 (stark@edith.com)"
    
    req = urllib.request.Request(url, headers=headers)
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    with opener.open(req, timeout=5) as response:
        return response.read(), response.info().get_content_type()

def ensure_local_libraries():
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    
    libraries = {
        "socket.io.min.js": "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js",
        "leaflet.js": "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js",
        "leaflet.css": "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"
    }
    
    for filename, url in libraries.items():
        filepath = os.path.join(static_dir, filename)
        if not os.path.exists(filepath):
            print(f"[SYSTEM] Downloading local library: {filename} from {url}...")
            try:
                data, _ = fetch_direct(url)
                with open(filepath, "wb") as f:
                    f.write(data)
                print(f"[SYSTEM] Successfully saved {filename} locally.")
            except Exception as e:
                print(f"[SYSTEM ERROR] Failed to download {filename}: {e}")

# --- EMITTERS ---
def emit_state(state_name, message=""):
    socketio.emit("state_change", {"state": state_name, "message": message})

def emit_chat(role, text):
    socketio.emit("chat_message", {"role": role, "text": text})

def emit_debug(text):
    socketio.emit("debug", {"text": text})

def emit_map(query):
    socketio.emit("map_search", {"query": query})

def emit_close_map():
    socketio.emit("close_map", {})

def emit_waveform(data):
    socketio.emit("waveform_data", {"samples": data})

def emit_audio(base64_data):
    socketio.emit("audio", {"data": base64_data})

def emit_music(video_id, title):
    socketio.emit("play_music", {"video_id": video_id, "title": title})

def emit_open_phone_app(app_name):
    socketio.emit("open_phone_app", {"app_name": app_name})

def emit_sysinfo(data):
    socketio.emit("sysinfo", data)

def emit_note(action, data):
    socketio.emit("note_event", {"action": action, "data": data})

def emit_timer(action, seconds=0, label=""):
    socketio.emit("timer_event", {"action": action, "seconds": seconds, "label": label})

def emit_weather(data):
    socketio.emit("weather_data", data)

def emit_alarm(data):
    socketio.emit("alarm_data", data)

def emit_kill_mode(active):
    socketio.emit("kill_mode", {"active": active})

def emit_world_briefing(data):
    socketio.emit("world_briefing", data)

def emit_close_world_briefing():
    socketio.emit("close_world_briefing", {})

# --- ROUTES ---
_memory_instance = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/memory", methods=["GET"])
def get_memory_data():
    if not _memory_instance:
        return Response(json.dumps({"error": "Memory instance offline"}), status=500, mimetype="application/json")
    try:
        data = {
            "facts": _memory_instance.get_all_facts(),
            "notes": _memory_instance.get_all_notes(),
            "corrections": _memory_instance.get_all_corrections(),
            "conversations": _memory_instance.get_all_conversations()
        }
        return Response(json.dumps(data, ensure_ascii=False), mimetype="application/json")
    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")

@app.route("/api/memory/<memory_type>/<path:item_id>", methods=["DELETE"])
def delete_memory_item(memory_type, item_id):
    if not _memory_instance:
        return Response(json.dumps({"error": "Memory instance offline"}), status=500, mimetype="application/json")
    try:
        if memory_type == "fact":
            _memory_instance.delete_fact_by_id(item_id)
        elif memory_type == "note":
            try:
                _memory_instance.delete_note(int(item_id))
            except ValueError:
                _memory_instance.delete_note(item_id)
        elif memory_type == "correction":
            _memory_instance.delete_correction_by_id(item_id)
        elif memory_type == "convo":
            _memory_instance.delete_convo_by_id(item_id)
        else:
            return Response(json.dumps({"error": f"Unknown memory type: {memory_type}"}), status=400, mimetype="application/json")
        return Response(json.dumps({"success": True}), mimetype="application/json")
    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")

@app.route("/api/geocode")
def geocode():
    from flask import request
    query = request.args.get("q", "")
    if not query:
        return json.dumps([])
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
        data, content_type = fetch_direct(url)
        return Response(data, mimetype=content_type)
    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")

@app.route("/api/tile/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    try:
        url = f"https://a.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png"
        data, content_type = fetch_direct(url)
        return Response(data, mimetype=content_type)
    except Exception as e:
        return Response(b"", status=404)

# --- SOCKET EVENTS ---
_typed_callback = None
_kill_toggle_callback = None
_wake_callback = None

mobile_sids = set()
mobile_sids_lock = threading.Lock()

def is_phone_connected():
    with mobile_sids_lock:
        return len(mobile_sids) > 0

@socketio.on("connect")
def handle_connect():
    from flask import request
    from edith.core.state import state, state_lock
    user_agent = request.headers.get("User-Agent", "").lower()
    # Detect Android Socket.IO connections
    if "okhttp" in user_agent or "android" in user_agent:
        with mobile_sids_lock:
            mobile_sids.add(request.sid)
        print(f"[SERVER] Mobile client connected. SID: {request.sid}. Total: {len(mobile_sids)}")
        
        # Flush buffered commands
        cmds_to_send = []
        with state_lock:
            if state.command_buffer:
                cmds_to_send = list(state.command_buffer)
                state.command_buffer.clear()
                
        if cmds_to_send:
            print(f"[SERVER] Flushing {len(cmds_to_send)} buffered commands to client.")
            for cmd in cmds_to_send:
                socketio.emit(cmd["event"], cmd["data"], to=request.sid)
    
    # Send current state to newly connected client
    socketio.emit("phone_mode_status", {"active": state.phone_mode})
    socketio.emit("kill_mode", {"active": state.kill_mode})

@socketio.on("disconnect")
def handle_disconnect():
    from flask import request
    with mobile_sids_lock:
        if request.sid in mobile_sids:
            mobile_sids.remove(request.sid)
            print(f"[SERVER] Mobile client disconnected. SID: {request.sid}. Total: {len(mobile_sids)}")

@socketio.on("typed_message")
def handle_typed(data):
    try:
        if _typed_callback:
            file_path = None
            if isinstance(data, str):
                try:
                    import json
                    parsed = json.loads(data)
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    pass
            
            if isinstance(data, dict):
                text = data.get("text", "")
                file_b64 = data.get("file", "")
                filename = data.get("filename", "uploaded_file.bin")
                if file_b64:
                    try:
                        import base64
                        import uuid
                        from pathlib import Path
                        if "," in file_b64:
                            file_b64 = file_b64.split(",", 1)[1]
                        file_bytes = base64.b64decode(file_b64)
                        
                        uploads_dir = Path(SESSION_DIR) / "uploads"
                        uploads_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Generate unique filename to avoid collision
                        safe_filename = f"{uuid.uuid4().hex}_{filename}"
                        saved_path = uploads_dir / safe_filename
                        with open(saved_path, "wb") as f:
                            f.write(file_bytes)
                        file_path = str(saved_path)
                        print(f"[SERVER] Successfully saved file from mobile client: {file_path}")
                    except Exception as fe:
                        print(f"[SERVER ERROR] Failed to save mobile client upload: {fe}")
            else:
                text = str(data)
            
            # Pass text and optional file_path to callback
            if file_path:
                _typed_callback(text, file_path=file_path)
            else:
                _typed_callback(text)
    except Exception as e:
        print(f"[ERROR in handle_typed] {e}")
        import traceback
        traceback.print_exc()

@socketio.on("kill_mode_toggle")
def handle_kill_toggle(data):
    if _kill_toggle_callback:
        _kill_toggle_callback(data.get("active", False))

@socketio.on("phone_mode_toggle")
def handle_phone_mode_toggle(data):
    from edith.core.state import state, state_lock
    active = data.get("active", False)
    with state_lock:
        state.phone_mode = active
    print(f"[SERVER] Phone Mode toggled to: {state.phone_mode}")
    socketio.emit("phone_mode_status", {"active": state.phone_mode})

@socketio.on("manual_wake")
def handle_manual_wake(*args):
    if _wake_callback:
        _wake_callback()

# --- Telemetry Ingest Handlers ---
import time
from edith.config import TELEMETRY_THROTTLE_MS, BATTERY_DROP_THRESHOLD, LOCATION_SHIFT_THRESHOLD_METERS

def is_throttled(event_name):
    from edith.core.state import state, state_lock
    with state_lock:
        now = time.time() * 1000
        last_time = state.last_telemetry_time.get(event_name, 0)
        if now - last_time < TELEMETRY_THROTTLE_MS:
            return True
        state.last_telemetry_time[event_name] = now
        return False

_last_app_notification_time = {}
_last_app_notification_lock = threading.Lock()

def _is_app_throttled(app_name):
    now = time.time() * 1000
    with _last_app_notification_lock:
        last_time = _last_app_notification_time.get(app_name, 0)
        if now - last_time < 2000:
            return True
        _last_app_notification_time[app_name] = now
        return False

def _is_garbage_notification(app_name, title, text):
    low_content = f"{app_name} {title} {text}".lower()
    garbage_keywords = [
        "downloading", "download complete", "syncing", "backup",
        "playing", "spotify", "music", "usb debugging", "charging",
        "running in the background", "whatsapp web is currently active",
        "checking for new messages", "updating", "installing"
    ]
    for kw in garbage_keywords:
        if kw in low_content:
            return True
    return False

@socketio.on("notification_received")
def handle_phone_notification(data):
    app_name = data.get("app", "your phone")
    title = data.get("title", "")
    text = data.get("text", "")
    
    # 1. Telemetry Classification Gate
    if _is_garbage_notification(app_name, title, text):
        print(f"[TELEMETRY GATE] Dropped low-value notification from {app_name}: {title}")
        return
        
    # 2. Prevent Event Flooding (Deduplication)
    if _is_app_throttled(app_name):
        print(f"[TELEMETRY GATE] Dropped duplicate notification from {app_name} (throttled)")
        return
    
    # Format notification
    announcement = f"[{app_name}] {title}"
    if text:
        announcement += f": {text}"
        
    try:
        print(f"[TELEMETRY] Standard notification logged silently: {announcement}")
    except UnicodeEncodeError:
        print(f"[TELEMETRY] Standard notification logged silently: {announcement.encode('ascii', 'ignore').decode('ascii')}")
    
    # 3. Queue for Event-Driven AI Evaluation (Silence-by-Default)
    from edith.core.state import state, state_lock
    
    # Store history for context
    with state_lock:
        state.recent_notifications.append(announcement)
        if len(state.recent_notifications) > 10:
            state.recent_notifications.pop(0)
            
    # Trigger the background evaluator
    state.telemetry_evaluation_queue.put({"type": "notification", "content": announcement})

@socketio.on("clipboard_changed")
def handle_clipboard_changed(data):
    if is_throttled("clipboard"): return
    from edith.core.state import state, state_lock
    content = data.get("content", "")
    if content:
        with state_lock:
            state.current_clipboard = content
        print(f"[SERVER] Mobile Clipboard Updated: {content[:30]}...")
        
        # Feature 3: Intelligent Clipboard Memory
        if len(content) > 150:
            state.telemetry_evaluation_queue.put({"type": "clipboard_summarize", "content": content})

@socketio.on("app_context_shifted")
def handle_app_context_shifted(data):
    if is_throttled("app_context"): return
    from edith.core.state import state, state_lock
    app_package = data.get("app_package", "")
    if app_package:
        with state_lock:
            state.foreground_app = app_package
        print(f"[SERVER] Foreground App Shifted: {app_package}")

@socketio.on("device_state_heartbeat")
def handle_device_state_heartbeat(data):
    from edith.core.state import state, state_lock
    with state_lock:
        old_batt = state.device_state.get("battery_level", 100)
        new_batt = data.get("battery_level", old_batt)
        
        # Dead-band filter for battery
        if abs(old_batt - new_batt) >= BATTERY_DROP_THRESHOLD:
            state.device_state["battery_level"] = new_batt
            print(f"[SERVER] Battery state updated: {new_batt}%")
            
        state.device_state["is_charging"] = data.get("is_charging", False)
        state.device_state["thermal_status"] = data.get("thermal_status", 0)
        
        # We can implement a haversine deadband for location here too if lat/lng are provided
        if "latitude" in data and "longitude" in data:
            state.device_state["latitude"] = data["latitude"]
            state.device_state["longitude"] = data["longitude"]
            
        # Feature 2: Proactive Morning Briefing
        import datetime
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        if 6 <= now.hour <= 10:
            if state.last_briefing_date != today_str:
                if time.time() - state.last_active_time > (5 * 3600):
                    state.last_briefing_date = today_str
                    state.telemetry_evaluation_queue.put({"type": "morning_briefing", "content": "Trigger morning briefing"})

def start_server(typed_cb, kill_cb, wake_cb, memory_obj=None):
    global _typed_callback, _kill_toggle_callback, _wake_callback, _memory_instance
    _typed_callback = typed_cb
    _kill_toggle_callback = kill_cb
    _wake_callback = wake_cb
    _memory_instance = memory_obj
    
    ensure_local_libraries()
    
    import traceback
    print(f"[SYSTEM] E.D.I.T.H. starting on http://localhost:{UI_PORT}")
    try:
        socketio.run(
            app, host="0.0.0.0", port=UI_PORT,
            debug=False, use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        print(f"[SERVER CRASH] {e}")
        traceback.print_exc()
    print("[SERVER] socketio.run() has exited.")
