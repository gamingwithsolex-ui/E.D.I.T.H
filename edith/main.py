import threading
import time
import webbrowser
import os
import sys

# ── GLOBAL PROXY BYPASS ──
# The system proxy (127.0.0.1:8892) is dead/blocking connections.
# Clear it from the environment so all HTTP clients (OpenAI, ElevenLabs) connect directly.
for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(key, None)

# Ensure the root directory is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edith.config import UI_PORT, SLEEP_TRIGGERS, SILENCE_LIMIT
from edith.core.state import state, set_state, state_lock
from edith.memory import Memory
from edith.core.brain import ask_edith, ensure_clients
from edith.interfaces.voice import start_voice_system, speak, listen
from edith.interfaces.web.server import (
    start_server, emit_state, emit_chat, emit_debug, 
    emit_map, emit_close_map, emit_waveform, emit_sysinfo,
    emit_note, emit_timer, emit_weather, emit_alarm, emit_kill_mode,
    emit_world_briefing, emit_close_world_briefing, emit_audio,
    emit_open_phone_app, emit_music
)
from edith.intents.detector import detect_and_act, AGENT_ROUTE, VISION_ROUTE
from edith.core.agent import run_agent_task
from edith.tools.system import get_system_info
from edith.tools.utils import cleanup

# Initialize Memory
memory = Memory()
memory.start_session()

SHUTDOWN_TRIGGERS = ["shutdown", "shut down", "exit", "quit", "power down", "going dark"]
STANDBY_TRIGGERS = ["go to sleep", "sleep", "goodnight", "goodbye", "standby", "good night"]
STOP_TRIGGERS = ["stop", "shut up", "be quiet", "silence", "stop talking", "hush", "stop speaking", "pause"]

def _process_typed(user_text, file_path=None):
    try:
        with state_lock:
            state.awake = True
            state.silence_count = 0
            state.last_active_time = time.time()
        with state_lock:
            if state.speaking:
                from edith.interfaces.voice import _tts_queue
                state.interrupt = True
                while not _tts_queue.empty():
                    try:
                        _tts_queue.get_nowait()
                        _tts_queue.task_done()
                    except Exception:
                        pass
                start_wait = time.time()
                while state.speaking and time.time() - start_wait < 3.0:
                    time.sleep(0.05)
                state.interrupt = False
        
        low_text = user_text.lower().strip()
        if low_text in STOP_TRIGGERS:
            emit_chat("edith", "[Speech Interrupted]")
            return
            
        if any(t in low_text for t in SHUTDOWN_TRIGGERS):
            speak("Powering down. Stay sharp.")
            time.sleep(2)
            with state_lock:
                state.running = False
            cleanup(memory)
            sys.exit(0)
            
        if any(t in low_text for t in STANDBY_TRIGGERS):
            speak("Going to standby. Call me if you need me.")
            with state_lock:
                state.awake = False
                state.silence_count = 0
            return
            
        emit_funcs = {
            "kill_mode": emit_kill_mode, "close_map": emit_close_map,
            "map": emit_map, "weather": emit_weather, "note": emit_note,
            "timer": emit_timer, "alarm": emit_alarm, "debug": emit_debug,
            "world_briefing": emit_world_briefing, "close_world_briefing": emit_close_world_briefing,
            "open_phone_app": emit_open_phone_app, "music": emit_music
        }
        
        context = detect_and_act(user_text, memory, emit_funcs)
        if context == AGENT_ROUTE and not file_path:
            emit_state("thinking")
            reply = run_agent_task(user_text, memory, emit_debug)
        elif context == VISION_ROUTE:
            from edith.tools.vision import capture_and_analyze_screen
            emit_debug("Capturing screen for visual analysis...")
            emit_state("thinking")
            reply = capture_and_analyze_screen()
        else:
            reply = ask_edith(user_text, memory, context, emit_debug, file_path=file_path)
        if reply:
            threading.Thread(target=speak, args=(reply,), daemon=True).start()
        
        # Clean up temporary uploaded file if it was created
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"[SYSTEM] Cleaned up temporary upload file: {file_path}")
            except Exception as ce:
                print(f"[SYSTEM ERROR] Failed to delete temporary upload: {ce}")
    except Exception as e:
        print(f"[ERROR in _process_typed] {e}")
        import traceback
        traceback.print_exc()


def handle_kill_toggle(active):
    state.kill_mode = active
    emit_kill_mode(state.kill_mode)
    mode_str = "ENGAGED" if state.kill_mode else "DISENGAGED"
    print("[KILL MODE] " + mode_str)
    emit_debug("Instant Kill Protocol " + mode_str)
    if state.kill_mode:
        emit_chat("edith", "Instant Kill Protocol engaged. No mercy. No filler. Let's work.")
    else:
        emit_chat("edith", "Standard mode restored. Back to being charming.")

def handle_manual_wake():
    with state_lock:
        if not state.awake:
            state.awake = True
            state.silence_count = 0
            state.last_active_time = time.time()
    emit_state("listening")
    speak("Online. What do you need?")

def sysinfo_loop():
    while state.running:
        try:
            info = get_system_info()
            if info:
                emit_sysinfo(info)
        except Exception as e:
            print(f"[SYSINFO ERROR] {e}")
        time.sleep(3)

def telemetry_worker():
    import queue
    from edith.core.brain import evaluate_telemetry
    from edith.interfaces.web.server import socketio, is_phone_connected
    
    while state.running:
        try:
            event = state.telemetry_evaluation_queue.get(timeout=1.0)
            telemetry_action = evaluate_telemetry(event, emit_debug)
            if telemetry_action:
                action_type = telemetry_action.get("action")
                action_data = telemetry_action.get("data", {})
                
                if action_type == "speak":
                    reply = action_data.get("text", "")
                    if reply: threading.Thread(target=speak, args=(reply,), daemon=True).start()
                elif action_type in ["execute_intent", "inject_ui_action", "run_shell_command"]:
                    if is_phone_connected():
                        socketio.emit(action_type, action_data)
                        emit_debug(f"Action dispatched: {action_type}")
                    else:
                        with state_lock:
                            state.command_buffer.append({"event": action_type, "data": action_data})
                        emit_debug(f"Action buffered: {action_type} (Mobile Disconnected)")
            
            state.telemetry_evaluation_queue.task_done()
        except queue.Empty:
            continue
        except Exception as te:
            print(f"[TELEMETRY EVAL ERROR] {te}")

def ai_loop():
    import traceback
    try:
        print("[DEBUG] ai_loop started. Sleeping 1 second...")
        time.sleep(1)
        print("[DEBUG] ai_loop calling ensure_clients()...")
        ensure_clients()
        print("[DEBUG] ensure_clients() finished.")
        
        emit_state("sleeping")
        print("[DEBUG] emit_state('sleeping') finished.")
        emit_debug("E.D.I.T.H. ready. Double clap or say 'Edith' to activate.")

        for note in memory.get_notes()[-10:]:
            emit_note("add", note)

        # Start Voice System
        start_voice_system(
            emit_chat=emit_chat,
            emit_state_func=emit_state,
            emit_debug=emit_debug,
            emit_waveform=emit_waveform,
            emit_mic_level=None, # Handled in voice.py
            emit_audio=emit_audio
        )
        
        threading.Thread(target=sysinfo_loop, daemon=True, name="SysInfo").start()
        threading.Thread(target=telemetry_worker, daemon=True, name="TelemetryWorker").start()

        print("\n+------------------------------------------------------+")
        print(f"|  E.D.I.T.H. — UI running at http://localhost:{UI_PORT}   |")
        print("|  WAKE  : Double clap OR say 'Edith'                  |")
        print("|  SLEEP : Say 'goodbye' or 'goodnight'                |")
        print("+------------------------------------------------------+\n")

        while state.running:
            if not state.awake or state.phone_mode:
                time.sleep(0.3); continue

            user_text = listen(emit_debug, emit_state)

            if user_text and state.speaking:
                import difflib
                # Check if it's just the microphone hearing the AI's own speakers
                ratio = difflib.SequenceMatcher(None, user_text, state.current_speech.lower()).ratio()
                if ratio > 0.35:
                    continue # Ignore echo
                
                # Genuine interruption!
                with state_lock:
                    state.interrupt = True
                
                # Clear the TTS queue immediately so she doesn't keep talking
                from edith.interfaces.voice import _tts_queue
                while not _tts_queue.empty():
                    try:
                        _tts_queue.get_nowait()
                        _tts_queue.task_done()
                    except Exception:
                        pass
                        
                # Wait for current audio file to finish stopping
                start_wait = time.time()
                while state.speaking and time.time() - start_wait < 3.0:
                    time.sleep(0.05)
                    
                with state_lock:
                    state.interrupt = False


            if not user_text:
                if state.speaking:
                    state.last_active_time = time.time()
                
                # Check inactivity timeout (45s)
                if time.time() - state.last_active_time >= 45.0:
                    speak("Going back to standby. I'll be here.")
                    with state_lock:
                        state.awake = False
                        state.silence_count = 0
                else:
                    time.sleep(0.5) # Prevent CPU spinning when mic fails or no speech heard
                continue

            with state_lock:
                state.silence_count = 0
                state.last_active_time = time.time()
            emit_chat("user", user_text)
            print("[YOU] " + user_text)

            low_text = user_text.lower().strip()
            if low_text in STOP_TRIGGERS:
                with state_lock:
                    state.interrupt = True
                from edith.interfaces.voice import _tts_queue
                while not _tts_queue.empty():
                    try:
                        _tts_queue.get_nowait()
                        _tts_queue.task_done()
                    except Exception:
                        pass
                start_wait = time.time()
                while state.speaking and time.time() - start_wait < 3.0:
                    time.sleep(0.05)
                with state_lock:
                    state.interrupt = False
                emit_chat("edith", "[Speech Interrupted]")
                continue

            if any(t in low_text for t in SHUTDOWN_TRIGGERS):
                speak("Acknowledged. E.D.I.T.H. going dark.")
                time.sleep(2)
                with state_lock:
                    state.running = False
                cleanup(memory)
                sys.exit(0) # Force exit
                break

            if any(t in low_text for t in STANDBY_TRIGGERS):
                speak("Going to standby. Call me if you need me.")
                with state_lock:
                    state.awake = False
                    state.silence_count = 0
                continue

            emit_funcs = {
                "kill_mode": emit_kill_mode, "close_map": emit_close_map,
                "map": emit_map, "weather": emit_weather, "note": emit_note,
                "timer": emit_timer, "alarm": emit_alarm, "debug": emit_debug,
                "world_briefing": emit_world_briefing, "close_world_briefing": emit_close_world_briefing,
                "open_phone_app": emit_open_phone_app, "music": emit_music
            }
            
            context = detect_and_act(user_text, memory, emit_funcs)
            if context == AGENT_ROUTE:
                emit_state("thinking")
                reply = run_agent_task(user_text, memory, emit_debug)
            elif context == VISION_ROUTE:
                from edith.tools.vision import capture_and_analyze_screen
                emit_debug("Capturing screen for visual analysis...")
                emit_state("thinking")
                reply = capture_and_analyze_screen()
            else:
                reply = ask_edith(user_text, memory, context, emit_debug)
            if reply:
                threading.Thread(target=speak, args=(reply,), daemon=True).start()
    except Exception as e:
        print(f"[FATAL AI LOOP ERROR] {e}")
        traceback.print_exc()

if __name__ == "__main__":
    import traceback as tb
    try:
        def open_browser():
            time.sleep(2)
            webbrowser.open(f"http://localhost:{UI_PORT}")
        
        threading.Thread(target=open_browser, daemon=True).start()
        threading.Thread(target=ai_loop, daemon=True, name="AILoop").start()
        
        start_server(typed_cb=_process_typed, kill_cb=handle_kill_toggle, wake_cb=handle_manual_wake, memory_obj=memory)
    except BaseException as e:
        if not isinstance(e, KeyboardInterrupt):
            print(f"[FATAL MAIN ERROR] {type(e).__name__}: {e}")
            tb.print_exc()
        input("Press Enter to exit...")
