import threading
import time
import queue as _queue

class State:
    def __init__(self):
        self.awake         = False
        self.running       = True
        self.speaking      = False
        self.interrupt     = False
        self.current_speech = ""
        self.silence_count = 0
        self.current       = "sleeping"
        self.kill_mode     = False
        self.phone_mode    = False
        self.last_active_time = time.time()
        self.recent_notifications = []
        self.is_online     = True
        self.active_model  = "INITIALIZING..."
        
        # Telemetry and Execution state
        self.current_clipboard = ""
        self.foreground_app = ""
        self.device_state = {}
        self.last_telemetry_time = {}
        self.command_buffer = [] # Queue for mobile commands
        self.telemetry_evaluation_queue = _queue.Queue()
        
        # Extended Context Memory
        self.last_briefing_date = None
        self.clipboard_summary = ""

state = State()
state_lock = threading.Lock()
mic_lock   = threading.Lock()   # Prevents mic contention between threads

def set_state(name, msg=""):
    with state_lock:
        state.current = name
