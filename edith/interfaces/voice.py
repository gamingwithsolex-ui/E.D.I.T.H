import re
import asyncio
import threading
import queue as _queue
import tempfile
import os
import shutil
import speech_recognition as sr
import numpy as np
import pyaudio
import time
from edith.config import VOICE_RATE, CLAP_THRESHOLD, CLAP_WINDOW, WAKE_WORDS, GEMINI_API_KEY, GEMINI_TTS_MODEL, GEMINI_TTS_VOICE
from edith.core.state import state, set_state, state_lock
from edith.interfaces.web.server import is_phone_connected

# =============================================================================
#  TTS — Fish Audio (Premium) with Edge TTS (Fallback)
# =============================================================================
_tts_queue = _queue.Queue()
_tts_thread = None

# Edge TTS fallback voice
EDGE_VOICE = "en-US-JennyNeural"

def _play_audio_file(filepath):
    """Play an audio file (MP3/WAV) using Windows native MCI for instant playback (0 latency)."""
    import os
    import time

    # Primary MCI Playback (Instant, Zero-Overhead)
    try:
        import ctypes
        alias = f"edith_voice_{int(time.time()*1000)}"
        mci = ctypes.windll.winmm.mciSendStringW
        
        mci_type = "waveaudio" if filepath.lower().endswith(".wav") else "mpegvideo"
        
        mci(f'close {alias}', None, 0, 0)
        mci(f'open "{filepath}" type {mci_type} alias {alias}', None, 0, 0)
        mci(f'play {alias}', None, 0, 0)
        
        buf = ctypes.create_unicode_buffer(256)
        while True:
            if state.interrupt:
                mci(f'stop {alias}', None, 0, 0)
                break
            mci(f'status {alias} mode', buf, 256, 0)
            if buf.value.lower() != "playing":
                break
            time.sleep(0.05)
            
        mci(f'close {alias}', None, 0, 0)
    except Exception as mci_ex:
        print(f"[VOICE] Legacy MCI playback failed: {mci_ex}")

def _speak_gemini_tts(text, emit_audio=None):
    """Generate speech via Google Gemini TTS API."""
    if not GEMINI_API_KEY:
        print("[VOICE] No Gemini API key found — skipping Gemini TTS.")
        return False
        
    try:
        import httpx
        import base64
        import wave
        
        # Strip emotional tags for Gemini TTS as they may not be parsed as SSML cleanly,
        # or keep them if needed. Usually, standard clean text works best.
        clean_text = _strip_all_tags(text)
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TTS_MODEL}:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": clean_text
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": GEMINI_TTS_VOICE
                        }
                    }
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        with httpx.Client(trust_env=False) as client:
            response = client.post(
                url,
                headers=headers,
                json=payload,
                timeout=5.0
            )
            
        if response.status_code != 200:
            print(f"[VOICE] Gemini TTS API error: {response.status_code} - {response.text} — falling back to Edge TTS.")
            return False
            
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            print(f"[VOICE] Gemini TTS returned no candidates. Response: {data}")
            return False
            
        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason not in ["STOP", "", None]:
            print(f"[VOICE] Gemini TTS candidate finish reason is: {finish_reason}. Response: {data}")
            
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        if not parts:
            print(f"[VOICE] Gemini TTS candidate has no parts. Response: {data}")
            return False
            
        part = parts[0]
        inline_data = part.get("inlineData", part.get("inline_data", {}))
        audio_base64 = inline_data.get("data", "")
        
        if not audio_base64:
            print("[VOICE] Gemini TTS returned empty audio data — falling back to Edge TTS.")
            return False
            
        audio_bytes = base64.b64decode(audio_base64)
        
        # Stream Base64 over Socket.IO to connected Android clients when phone mode is active
        if emit_audio and state.phone_mode:
            try:
                emit_audio(audio_base64)
            except Exception as e:
                print(f"[VOICE] Error emitting audio to Socket.IO: {e}")
        
        # Save to temp WAV file
        tmp_path = os.path.join(tempfile.gettempdir(), f"edith_gemini_{int(time.time()*1000)}.wav")
        with wave.open(tmp_path, "wb") as wav_file:
            wav_file.setnchannels(1)       # Mono
            wav_file.setsampwidth(2)      # 16-bit (2 bytes)
            wav_file.setframerate(24000)  # 24kHz
            wav_file.writeframes(audio_bytes)
            
        if not (is_phone_connected() and state.phone_mode):
            _play_audio_file(tmp_path)
        else:
            print("[VOICE] Phone connected and Phone Mode Active — muting PC speaker.")
        try: os.remove(tmp_path)
        except OSError: pass
        return True
    except Exception as e:
        print(f"[VOICE] Gemini TTS error: {e} — falling back.")
        return False

_kokoro = None
def _speak_kokoro_tts(text, emit_audio=None):
    """Local offline TTS using Kokoro fallback."""
    global _kokoro
    try:
        if _kokoro is None:
            from edith.speech.kokoro_tts import KokoroTTSBackend
            _kokoro = KokoroTTSBackend()
            
        if not _kokoro.health():
            return False
            
        result = _kokoro.synthesize(text, voice_id="af_heart")
        if not result or not result.audio:
            return False
            
        import tempfile
        import time
        tmp_path = os.path.join(tempfile.gettempdir(), f"edith_kokoro_{int(time.time()*1000)}.wav")
        with open(tmp_path, "wb") as f:
            f.write(result.audio)
        
        if not (is_phone_connected() and state.phone_mode):
            _play_audio_file(tmp_path)
            
        try: os.remove(tmp_path)
        except OSError: pass
        return True
    except Exception as e:
        print(f"[VOICE] Kokoro TTS fallback error: {e}")
        return False

async def _edge_tts_speak(text, emit_audio=None):
    """Fallback: Edge TTS (fast, free, reliable — but no emotional expressions)."""
    try:
        import edge_tts
        import base64
        communicate = edge_tts.Communicate(text, EDGE_VOICE)
        tmp_path = os.path.join(tempfile.gettempdir(), f"edith_edge_tts_{int(time.time()*1000)}.mp3")
        await communicate.save(tmp_path)
        
        if emit_audio and state.phone_mode:
            try:
                with open(tmp_path, "rb") as f:
                    audio_bytes = f.read()
                    b64 = base64.b64encode(audio_bytes).decode('utf-8')
                    emit_audio(b64)
            except Exception as e:
                print(f"[VOICE] Error emitting Edge TTS audio to Socket.IO: {e}")
                
        if not (is_phone_connected() and state.phone_mode):
            _play_audio_file(tmp_path)
        else:
            print("[VOICE] Phone connected and Phone Mode Active — muting PC speaker.")
        try: os.remove(tmp_path)
        except OSError: pass
    except Exception as e:
        print(f"[VOICE] Edge TTS Fallback Error: {e}")

def _strip_all_tags(text):
    """Remove ALL bracket tags — for Edge TTS which reads them as literal text."""
    return re.sub(r'\[[\w\s]+\]', '', text).strip()


def _tts_worker(emit_chat, emit_state_func, emit_audio=None):
    print(f"[VOICE] Gemini TTS ({GEMINI_TTS_MODEL} with voice {GEMINI_TTS_VOICE}) + Edge TTS (fallback) ready.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    tts_network_timed_out = False

    while True:
        try:
            text = _tts_queue.get(timeout=1)
            if text is None:
                break
                
            if state.interrupt:
                _tts_queue.task_done()
                continue
                
            state.speaking = True
            state.current_speech = text
            emit_state_func("speaking", text[:60])
            if emit_chat:
                emit_chat("edith", text)
            try:
                print("[EDITH] " + text)
            except UnicodeEncodeError:
                print("[EDITH] " + text.encode("ascii", errors="ignore").decode())

            # 1. Offline Mode Routing
            if not getattr(state, "is_online", True) or tts_network_timed_out:
                if tts_network_timed_out:
                    print("[VOICE] Network timed out previously. Routing instantly to Kokoro TTS.")
                else:
                    print("[VOICE] Offline mode detected. Routing to Kokoro TTS.")
                success = False
                try:
                    success = _speak_kokoro_tts(text, emit_audio)
                except Exception as e:
                    print(f"[VOICE] Kokoro offline TTS failed: {e}")
                
                # If Kokoro fails while offline, we just continue (or Edge TTS which will fail anyway)
                if not success:
                    _tts_queue.task_done()
                    continue

            else:
                # 2. Online Mode Routing: Try Gemini TTS first
                success = False
                try:
                    success = _speak_gemini_tts(text, emit_audio)
                except Exception as e:
                    err_str = str(e).lower()
                    if "timeout" in err_str or "connect" in err_str:
                        tts_network_timed_out = True
                    print(f"[VOICE] Gemini TTS failed: {e}")

            # Fallback to Edge TTS first (fastest online fallback)
            if not success and not getattr(state, "is_online", True) == False and not tts_network_timed_out:
                try:
                    edge_text = _strip_all_tags(text)
                    loop.run_until_complete(_edge_tts_speak(edge_text, emit_audio))
                    success = True
                except Exception as e:
                    print(f"[VOICE] Edge TTS failed: {e}")

            # Try Kokoro local offline fallback if all else fails
            if not success:
                try:
                    success = _speak_kokoro_tts(text, emit_audio)
                except Exception as e:
                    print(f"[VOICE] Kokoro TTS fallback failed: {e}")

            state.speaking = False
            if state.awake:
                emit_state_func("listening")
            else:
                emit_state_func("sleeping")
            _tts_queue.task_done()
        except _queue.Empty:
            continue


def speak(text):
    """Clean markdown and queue text for neural voice output."""
    clean = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", text)
    clean = re.sub(r"#{1,6}\s", "", clean)
    clean = re.sub(r"`([^`]+)`", r"\1", clean)
    clean = re.sub(r"\n+", " ", clean)
    _tts_queue.put(clean)



# =============================================================================
#  STT — Google Speech Recognition (mic exclusive to this module)
# =============================================================================
_rec = sr.Recognizer()
_rec.pause_threshold   = 0.7
_rec.dynamic_energy_threshold = True

# A simple threading lock to ensure only one thread uses the mic at a time
_mic_lock = threading.Lock()

_whisper_model = None
def _recognize_local_whisper(audio_data):
    """Local offline STT using faster-whisper."""
    global _whisper_model
    try:
        from faster_whisper import WhisperModel
        import io
        if _whisper_model is None:
            # Load tiny model on CPU for low latency and minimal resource usage
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        
        wav_data = io.BytesIO(audio_data.get_wav_data())
        segments, info = _whisper_model.transcribe(wav_data, beam_size=1)
        text = " ".join([segment.text for segment in segments])
        return text.strip().lower()
    except Exception as e:
        print(f"[VOICE] Local Whisper transcription error: {e}")
        return ""

def listen(emit_debug=None, emit_state_func=None):
    """Actively listen for a single voice command (called when AWAKE)."""
    if emit_state_func:
        emit_state_func("listening")
    with _mic_lock:
        try:
            with sr.Microphone() as src:
                _rec.adjust_for_ambient_noise(src, duration=0.1)
                audio = _rec.listen(src, timeout=6, phrase_time_limit=12)
                
                # Try local Whisper first
                text = _recognize_local_whisper(audio)
                if not text:
                    # Fallback to cloud Google recognition
                    text = _rec.recognize_google(audio).lower()
                
                if emit_debug:
                    emit_debug("You said: " + text)
                return text
        except Exception:
            return ""


# =============================================================================
#  MIC AVAILABILITY CHECK
# =============================================================================
def _check_mic():
    """Returns True if a working microphone is available. Safe — no C-level crash."""
    try:
        p = pyaudio.PyAudio()
        info = p.get_default_input_device_info()
        # Try opening a tiny stream to confirm it actually works
        s = p.open(format=pyaudio.paInt16, channels=1, rate=16000,
                   input=True, frames_per_buffer=512,
                   input_device_index=int(info["index"]))
        s.stop_stream()
        s.close()
        # Only terminate after a successful open/close
        p.terminate()
        return True
    except Exception as e:
        print(f"[VOICE] Mic check failed: {e}")
        # Do NOT call p.terminate() here — PortAudio segfaults on a failed open
        return False


def _wake_loop():
    _calibrated  = False
    _warned      = False
    _retry_delay = 0.05  # Backs off to 5s on repeated mic failures
    while state.running:
        if state.awake or state.speaking or state.phone_mode:
            time.sleep(0.2)
            continue
        if not _mic_lock.acquire(timeout=0.5):
            continue
        try:
            with sr.Microphone() as src:
                if not _calibrated:
                    _rec.adjust_for_ambient_noise(src, duration=0.5)
                    _calibrated = True
                _warned      = False
                _retry_delay = 0.05
                try:
                    audio = _rec.listen(src, timeout=2, phrase_time_limit=3)
                    heard = _recognize_local_whisper(audio)
                    if not heard:
                        heard = _rec.recognize_google(audio).lower()
                    
                    if any(w in heard for w in WAKE_WORDS):
                        with state_lock:
                            if not state.awake:
                                state.awake = True
                                state.silence_count = 0
                                state.last_active_time = time.time()
                        speak("E.D.I.T.H. online. Ready.")
                except Exception:
                    pass  # Timeout/no speech — normal, keep looping
        except Exception as e:
            if not _warned:
                print(f"[WAKE] Mic unavailable ({e}) — retrying...")
                _warned      = True
                _retry_delay = min(_retry_delay * 2, 5.0)  # Exponential back-off up to 5s
            time.sleep(_retry_delay)
        finally:
            try:
                _mic_lock.release()
            except RuntimeError:
                pass
        time.sleep(0.05)


# =============================================================================
#  CLAP DETECTOR — Listens for double-clap via raw audio amplitude (no STT)
#  Runs fully independently from the wake loop (separate PyAudio instance)
# =============================================================================
def _clap_loop(emit_waveform):
    p = None
    stream = None
    try:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        print("[VOICE] Clap detector online.")
    except Exception as e:
        print(f"[VOICE] Clap detector unavailable: {e} — wake word only mode.")
        # CRITICAL: Do NOT call p.terminate() after a failed p.open() —
        # it causes a C-level PortAudio segfault that kills the whole process.
        # Just discard the PyAudio object safely.
        p = None
        return

    clap_times = []
    last_clap   = 0

    while state.running:
        if state.speaking or state.awake or state.phone_mode:
            time.sleep(0.1)
            continue
        try:
            data    = stream.read(1024, exception_on_overflow=False)
            samples = np.frombuffer(data, dtype=np.int16)
            amp     = int(np.max(np.abs(samples)))

            if emit_waveform:
                emit_waveform(samples[::32][:32].tolist())

            if amp > CLAP_THRESHOLD:
                now = time.time()
                if now - last_clap > 0.12:
                    last_clap = now
                    clap_times.append(now)
                    clap_times = [t for t in clap_times if now - t <= CLAP_WINDOW]
                    if len(clap_times) >= 2:
                        clap_times = []
                        with state_lock:
                            if not state.awake:
                                state.awake = True
                                state.silence_count = 0
                                state.last_active_time = time.time()
                        speak("Online. What do you need?")
        except Exception:
            time.sleep(0.3)

    try:
        stream.stop_stream()
        stream.close()
        p.terminate()
    except Exception:
        pass


# =============================================================================
#  ENTRY POINT
# =============================================================================
def start_voice_system(emit_chat, emit_state_func, emit_debug, emit_waveform, emit_mic_level, emit_audio=None):
    # Always start TTS — it doesn't need a mic
    threading.Thread(target=_tts_worker, args=(emit_chat, emit_state_func, emit_audio), daemon=True, name="TTS").start()

    # Gate ALL mic threads behind a safe hardware check
    mic_available = _check_mic()

    if mic_available:
        print("[VOICE] Microphone confirmed — starting wake word detection.")
        threading.Thread(target=_wake_loop, daemon=True, name="WakeWord").start()
        # threading.Thread(target=_clap_loop, args=(emit_waveform,), daemon=True, name="ClapDetect").start()
    else:
        # No mic — skip all audio input threads and boot in text-only mode
        print("[VOICE] No microphone detected — booting in TEXT-ONLY mode.")
        print("[VOICE] Use the web UI at http://localhost:5001 to chat.")
        with state_lock:
            state.awake         = True   # Always awake — no wake word needed
            state.silence_count = 0
        emit_state_func("listening")
