import os
import shutil
import glob
import tempfile
from pathlib import Path
from edith.config import SESSION_DIR

def cleanup(memory):
    print("[SYSTEM] Cleaning session files...")
    memory.save_session_log()
    if SESSION_DIR.exists():
        try:
            shutil.rmtree(SESSION_DIR)
        except Exception:
            pass
    for pattern in [
        str(Path(tempfile.gettempdir()) / "edith_*.png"),
        str(Path(tempfile.gettempdir()) / "edith_*.tmp"),
        str(Path(tempfile.gettempdir()) / "edith_*.mp3"),
        str(Path(tempfile.gettempdir()) / "edith_*.wav"),
    ]:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except Exception:
                pass
    memory.save()
    print("[SYSTEM] Clean. Memory saved. Session logged. Going dark.")
