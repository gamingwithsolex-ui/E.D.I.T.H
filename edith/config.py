import os
from pathlib import Path
import tempfile

# ==============================================================
# CONFIGURATION
# ==============================================================
# Load .env manually to avoid extra dependencies if not installed
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            # Trim inline comments
            v_clean = ""
            in_quote = None
            for char in v:
                if char in ('"', "'"):
                    if in_quote == char:
                        in_quote = None
                    elif in_quote is None:
                        in_quote = char
                elif char == "#" and in_quote is None:
                    break
                v_clean += char
            v = v_clean.strip()
            # Strip outer quotes
            if len(v) >= 2 and ((v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'"))):
                v = v[1:-1]
            os.environ[k.strip()] = v.strip()

load_env()

# LLM API Configs
# LLM API Configs
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MAIN_MODEL   = "gemini-2.5-flash"
HF_TOKEN       = os.environ.get("HF_TOKEN", "")
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")
FISH_VOICE_ID = os.environ.get("FISH_VOICE_ID", "")

# Local Model / Hybrid Configs
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
LOCAL_MODEL_NAME = os.environ.get("LOCAL_MODEL_NAME", "llama3.2")

# Telemetry Dead-Band Thresholds
TELEMETRY_THROTTLE_MS = 2000  # Minimum time between identical telemetry updates
BATTERY_DROP_THRESHOLD = 5.0  # Only trigger context update if battery drops by >5%
LOCATION_SHIFT_THRESHOLD_METERS = 50.0 # Only trigger on significant movement

# Gemini TTS Configs
GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_VOICE = "Aoede" # Default prebuilt voice: Aoede, Kore, Puck, Charon, Fenrir

# Second Brain (DeepSeek V4 Pro)
DEEPSEEK_API_KEY     = os.environ.get("DEEPSEEK_API_KEY", "")
STRATEGIC_MODEL      = "deepseek-ai/deepseek-v4-pro"  # DeepSeek V4 Pro on Nvidia NIM
AI_NAME        = "Edith"
VOICE_RATE     = 155   # Slightly measured — matches EDITH's precise delivery
CLAP_THRESHOLD = 2000
CLAP_WINDOW    = 1.0
SILENCE_LIMIT  = 3
UI_PORT        = 5001

# Paths
MEMORY_FILE = Path.home() / ".edith_memory.json"
CHROMA_DIR = Path.home() / ".edith_chroma_db"
CONVO_LOG_DIR = Path.home() / ".edith_conversations"
SESSION_DIR = Path(tempfile.gettempdir()) / "edith_session"

# Triggers
WAKE_WORDS  = ["edith", "hey edith", "ok edith", "okay edith", "wake up edith", "e.d.i.t.h", "wake up daddy's home"]
SLEEP_TRIGGERS = [
    "goodbye", "good bye", "good night", "goodnight",
    "bye", "see you", "see ya", "go to sleep",
    "close", "shut down", "shutdown", "exit", "quit",
    "stop", "turn off", "thats all", "that's all", "sleep",
]

APP_MAP = {
    "chrome": "chrome", "google chrome": "chrome",
    "firefox": "firefox", "notepad": "notepad",
    "calculator": "calc", "vs code": "code", "vscode": "code",
    "spotify": "spotify", "discord": "discord",
    "file explorer": "explorer", "explorer": "explorer",
    "paint": "mspaint", "word": "winword", "excel": "excel",
    "task manager": "taskmgr", "cmd": "cmd",
    "terminal": "cmd", "powershell": "powershell",
    "vlc": "vlc", "steam": "steam",
    "whatsapp": "whatsapp:",
}

# ── Agentic Task Engine ───────────────────────────────────────
AGENT_MAX_STEPS           = 10          # Maximum tool calls per agentic task
AGENT_CONFIRM_DESTRUCTIVE = True        # Ask before delete/kill operations
AGENT_WORKING_DIR         = str(Path.home())  # Default working directory
