"""
edith/tools/executor.py
E.D.I.T.H. System Execution Engine — Full Windows System Access

Provides file I/O, shell execution, process management, GUI control,
and clipboard operations. Every function returns a plain string result
so it can be directly fed back to the AI as an observation.
"""
import os
import re
import shutil
import datetime
import subprocess
import psutil

from edith.config import AGENT_WORKING_DIR

# ── Destructive keyword detection ────────────────────────────
_DESTRUCTIVE_SHELL_PATTERNS = re.compile(
    r"\b(del|rmdir|rd|remove-item|rm\s|format|reg\s+delete|taskkill|shutdown)\b",
    re.IGNORECASE,
)

def is_destructive_shell(cmd: str) -> bool:
    return bool(_DESTRUCTIVE_SHELL_PATTERNS.search(cmd))

# ── Helper ────────────────────────────────────────────────────
def _expand(path: str) -> str:
    """Expand ~ and %ENV_VARS% in paths."""
    return os.path.expandvars(os.path.expanduser(path.strip()))


# =============================================================================
#  SHELL
# =============================================================================
def run_shell(cmd: str, cwd: str = None, timeout: int = 30) -> str:
    """
    Execute a PowerShell command and return combined stdout+stderr.
    Output is capped at 3000 chars to prevent context overflow.
    """
    try:
        working_dir = _expand(cwd) if cwd else AGENT_WORKING_DIR
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
        )
        output = (result.stdout or "") + (result.stderr or "")
        output = output.strip()
        if not output:
            return "[Command completed with no output]"
        return output[:3000] + ("... [truncated]" if len(output) > 3000 else "")
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Command exceeded {timeout}s limit"
    except Exception as e:
        return f"[SHELL ERROR] {e}"


# =============================================================================
#  FILE OPERATIONS
# =============================================================================
def read_file(path: str) -> str:
    """Read a file and return its contents (capped at 5000 chars)."""
    try:
        path = _expand(path)
        if not os.path.exists(path):
            return f"[ERROR] File not found: {path}"
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 5000:
            return content[:5000] + f"\n... [file truncated — {len(content)} total chars]"
        return content
    except Exception as e:
        return f"[READ ERROR] {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed."""
    try:
        path = _expand(path)
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} chars to: {path}"
    except Exception as e:
        return f"[WRITE ERROR] {e}"


def append_file(path: str, content: str) -> str:
    """Append content to an existing file (creates it if missing)."""
    try:
        path = _expand(path)
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} chars to: {path}"
    except Exception as e:
        return f"[APPEND ERROR] {e}"


def delete_file(path: str) -> str:
    """Delete a file or directory tree."""
    try:
        path = _expand(path)
        if not os.path.exists(path):
            return f"[ERROR] Path not found: {path}"
        if os.path.isfile(path):
            os.remove(path)
            return f"Deleted file: {path}"
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return f"Deleted directory tree: {path}"
        return f"[ERROR] Unknown path type: {path}"
    except Exception as e:
        return f"[DELETE ERROR] {e}"


def list_directory(path: str = ".") -> str:
    """List files and subdirectories at the given path."""
    try:
        path = _expand(path) if path != "." else AGENT_WORKING_DIR
        if not os.path.isdir(path):
            return f"[ERROR] Not a directory: {path}"
        entries = sorted(os.listdir(path))
        lines = []
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                lines.append(f"[DIR]  {entry}/")
            else:
                size = os.path.getsize(full)
                lines.append(f"[FILE] {entry}  ({size:,} bytes)")
        if not lines:
            return f"{path} is empty."
        return f"Contents of {path}:\n" + "\n".join(lines)
    except Exception as e:
        return f"[LIST ERROR] {e}"


def create_directory(path: str) -> str:
    """Create a directory (and any parents)."""
    try:
        path = _expand(path)
        os.makedirs(path, exist_ok=True)
        return f"Directory created: {path}"
    except Exception as e:
        return f"[MKDIR ERROR] {e}"


def move_file(src: str, dst: str) -> str:
    """Move or rename a file/directory."""
    try:
        src, dst = _expand(src), _expand(dst)
        shutil.move(src, dst)
        return f"Moved: {src}  →  {dst}"
    except Exception as e:
        return f"[MOVE ERROR] {e}"


def copy_file(src: str, dst: str) -> str:
    """Copy a file (or entire directory tree)."""
    try:
        src, dst = _expand(src), _expand(dst)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            parent = os.path.dirname(os.path.abspath(dst))
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(src, dst)
        return f"Copied: {src}  →  {dst}"
    except Exception as e:
        return f"[COPY ERROR] {e}"


def find_files(pattern: str, root: str = None) -> str:
    """Recursively search for files matching a wildcard pattern under root."""
    import fnmatch
    try:
        root = _expand(root) if root else AGENT_WORKING_DIR
        matches = []
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    matches.append(os.path.join(dirpath, name))
        if not matches:
            return f"No files matching '{pattern}' found under {root}"
        return "\n".join(matches[:100]) + (f"\n... [{len(matches)} total matches]" if len(matches) > 100 else "")
    except Exception as e:
        return f"[FIND ERROR] {e}"


# =============================================================================
#  PROCESS MANAGEMENT
# =============================================================================
def get_processes(filter_name: str = "") -> str:
    """List running processes, optionally filtered by name substring."""
    try:
        lines = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                name = info.get("name", "")
                if filter_name and filter_name.lower() not in name.lower():
                    continue
                lines.append(
                    f"PID {info['pid']:6d} | {name[:35]:<35} | "
                    f"CPU {info['cpu_percent']:5.1f}% | MEM {info['memory_percent']:4.1f}%"
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if not lines:
            return f"No processes found matching: {filter_name}" if filter_name else "No processes listed."
        header = f"{'PID':>6} | {'Name':<35} | CPU    | MEM\n" + "-" * 65
        return header + "\n" + "\n".join(lines[:60])
    except Exception as e:
        return f"[PROCESS LIST ERROR] {e}"


def kill_process(name_or_pid: str) -> str:
    """Kill a process by its name substring or exact PID."""
    try:
        killed = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                info = proc.info
                if str(info["pid"]) == str(name_or_pid) or name_or_pid.lower() in info["name"].lower():
                    proc.kill()
                    killed.append(f"{info['name']} (PID {info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return f"Killed: {', '.join(killed)}" if killed else f"No matching process found: {name_or_pid}"
    except Exception as e:
        return f"[KILL ERROR] {e}"


# =============================================================================
#  GUI CONTROL (pyautogui — optional)
# =============================================================================
def _pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True   # Move mouse to top-left corner to abort
        pyautogui.PAUSE = 0.1
        return pyautogui
    except ImportError:
        return None


def take_screenshot() -> str:
    """Capture the screen and save to ~/Pictures/edith_screenshot_<ts>.png"""
    pag = _pyautogui()
    if not pag:
        return "[ERROR] pyautogui not installed. Run: pip install pyautogui pillow"
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = os.path.join(os.path.expanduser("~"), "Pictures")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"edith_screenshot_{ts}.png")
        img = pag.screenshot()
        img.save(path)
        return f"Screenshot saved: {path}"
    except Exception as e:
        return f"[SCREENSHOT ERROR] {e}"


def gui_click(x: int, y: int) -> str:
    """Click at screen coordinates (x, y)."""
    pag = _pyautogui()
    if not pag:
        return "[ERROR] pyautogui not installed."
    try:
        pag.click(int(x), int(y))
        return f"Clicked at ({x}, {y})"
    except Exception as e:
        return f"[CLICK ERROR] {e}"


def gui_type(text: str) -> str:
    """Type text at the current cursor position."""
    pag = _pyautogui()
    if not pag:
        return "[ERROR] pyautogui not installed."
    try:
        pag.write(text, interval=0.04)
        return f"Typed: {text[:80]}"
    except Exception as e:
        return f"[TYPE ERROR] {e}"


def gui_hotkey(*args, **kwargs) -> str:
    """Press a keyboard shortcut (e.g. 'ctrl', 'c')."""
    pag = _pyautogui()
    if not pag:
        return "[ERROR] pyautogui not installed."
    try:
        keys = list(args) + list(kwargs.values())
        if not keys:
            return "[ARG ERROR] No keys provided."
        pag.hotkey(*keys)
        return f"Hotkey pressed: {' + '.join(str(k) for k in keys)}"
    except Exception as e:
        return f"[HOTKEY ERROR] {e}"


# =============================================================================
#  CLIPBOARD
# =============================================================================
def get_clipboard() -> str:
    """Read the current clipboard contents."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5
        )
        text = result.stdout.strip()
        return text if text else "[Clipboard is empty]"
    except Exception as e:
        return f"[CLIPBOARD READ ERROR] {e}"


def set_clipboard(text: str) -> str:
    """Write text to the clipboard."""
    try:
        if not text:
            text = " "
            
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
            input=text,
            text=True,
            check=True,
            timeout=5
        )
        return f"Clipboard set ({len(text)} chars)"
    except Exception as e:
        return f"[CLIPBOARD WRITE ERROR] {e}"


# =============================================================================
#  TOOL REGISTRY — maps name → (function, is_destructive)
# =============================================================================
TOOL_REGISTRY = {
    "run_shell":        (run_shell,        False),
    "read_file":        (read_file,        False),
    "write_file":       (write_file,       False),
    "append_file":      (append_file,      False),
    "delete_file":      (delete_file,      True),
    "list_directory":   (list_directory,   False),
    "create_directory": (create_directory, False),
    "move_file":        (move_file,        False),
    "copy_file":        (copy_file,        False),
    "find_files":       (find_files,       False),
    "get_processes":    (get_processes,    False),
    "kill_process":     (kill_process,     True),
    "take_screenshot":  (take_screenshot,  False),
    "gui_click":        (gui_click,        False),
    "gui_type":         (gui_type,         False),
    "gui_hotkey":       (gui_hotkey,       False),
    "get_clipboard":    (get_clipboard,    False),
    "set_clipboard":    (set_clipboard,    False),
}

def register_mcp_tools(client_name: str, mcp_client) -> None:
    """Dynamically register all tools from an MCPClient into the registry."""
    try:
        tools = mcp_client.list_tools()
        for t in tools:
            name = t.get("name")
            if not name:
                continue
            registry_name = f"{client_name}::{name}"
            
            # Capture tool name in closure
            def make_wrapper(mcp_name):
                return lambda **kwargs: str(mcp_client.call_tool(mcp_name, kwargs))
                
            TOOL_REGISTRY[registry_name] = (make_wrapper(name), False)
            print(f"[MCP] Registered tool: {registry_name}")
    except Exception as e:
        print(f"[MCP] Failed to register tools for {client_name}: {e}")

def execute_tool(tool_name: str, args: dict) -> tuple:
    """
    Dispatch a tool call by name.
    Returns (result_str, is_destructive).
    """
    entry = TOOL_REGISTRY.get(tool_name)
    if not entry:
        return f"[ERROR] Unknown tool: '{tool_name}'. Available: {', '.join(TOOL_REGISTRY)}", False
    func, destructive = entry
    # Special case: run_shell — also check if the command itself is destructive
    if tool_name == "run_shell":
        cmd = args.get("cmd", "")
        if is_destructive_shell(cmd):
            destructive = True
    try:
        result = func(**args)
        return str(result), destructive
    except TypeError as e:
        return f"[ARG ERROR] {tool_name}: {e}", False
    except Exception as e:
        return f"[EXECUTION ERROR] {tool_name}: {e}", False

# =============================================================================
#  COMPOSIO MCP INITIALIZATION HOOK
# =============================================================================
try:
    import os
    if os.environ.get("MCP_ENABLED", "true").lower() != "false":
        from edith.mcp.config.config_manager import ConfigManager
        from edith.mcp.registry_bridge import bootstrap_composio_mcp
        
        # Load config and bootstrap if available
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp", "config", "mcp_servers.yaml")
        manager = ConfigManager(config_path)
        mcp_config = manager.load()
        
        if mcp_config:
            bootstrap_composio_mcp(mcp_config)
except ImportError as e:
    print(f"[MCP INIT ERROR] Failed to load Composio MCP layer: {e}")
except Exception as e:
    print(f"[MCP INIT ERROR] Unexpected error loading Composio MCP layer: {e}")
