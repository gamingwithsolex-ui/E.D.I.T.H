"""
edith/sandbox/runner.py
Secure sandbox execution environment for running LLM-generated code.
Supports Docker runtime and falls back to a path-validated, environment-restricted subprocess jail.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Security blocked patterns to prevent accessing sensitive files
BLOCKED_PATTERNS = [
    ".ssh", ".gnupg", ".env", "credentials", "id_rsa", "id_ed25519",
    ".aws", ".config/gcloud", "*.pem", "*.key", "*.p12", "*.pfx",
    ".git/config", "shadow", "passwd", "token", "secret",
    ".docker/config.json", ".kube/config", ".npmrc", ".pypirc"
]

def is_path_blocked(path_str: str) -> bool:
    """Check if the path contains any blocked components/patterns."""
    try:
        resolved = Path(path_str).resolve()
        parts = resolved.parts
        name = resolved.name
        
        for pattern in BLOCKED_PATTERNS:
            if fnmatch.fnmatch(name, pattern):
                return True
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False
    except Exception:
        return True  # Block on error

class SandboxRunner:
    """Manages secure execution of python code blocks."""

    def __init__(self, timeout: int = 30, use_docker: bool = False) -> None:
        self.timeout = timeout
        self.use_docker = use_docker
        self.has_docker = self._detect_docker() if use_docker else False

    def _detect_docker(self) -> bool:
        """Check if docker is available and running."""
        try:
            path = shutil.which("docker")
            if path is None:
                return False
            # Verify daemon is running
            res = subprocess.run([path, "info"], capture_output=True, timeout=2)
            return res.returncode == 0
        except Exception:
            return False

    def run_python_code(
        self,
        code: str,
        env: Optional[Dict[str, str]] = None,
        workspace: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute Python code in the sandbox. Returns stdout, stderr, and metadata."""
        if self.use_docker and self.has_docker:
            return self._run_in_docker(code, env, workspace)
        else:
            return self._run_in_subprocess_jail(code, env, workspace)

    def _run_in_docker(
        self,
        code: str,
        env: Optional[Dict[str, str]] = None,
        workspace: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs the code inside a Docker container using python:3.11-slim."""
        container_name = f"edith-sandbox-{uuid.uuid4().hex[:12]}"
        temp_dir = tempfile.mkdtemp(prefix="edith_docker_")
        script_path = os.path.join(temp_dir, "script.py")
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        docker_args = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "none",
            "-v", f"{temp_dir}:/workspace",
            "-w", "/workspace",
        ]

        # Inject sanitised environments
        docker_env = {"PYTHONUNBUFFERED": "1"}
        if env:
            for k, v in env.items():
                if not is_path_blocked(k) and not is_path_blocked(v):
                    docker_env[k] = v

        for k, v in docker_env.items():
            docker_args.extend(["-e", f"{k}={v}"])

        docker_args.extend(["python:3.11-slim", "python", "script.py"])

        t0 = time.time()
        try:
            proc = subprocess.run(
                docker_args,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            duration = time.time() - t0
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "duration": duration,
                "mode": "docker"
            }
        except subprocess.TimeoutExpired:
            # Clean up the container
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Process timed out after {self.timeout}s.",
                "duration": self.timeout,
                "mode": "docker"
            }
        finally:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

    def _run_in_subprocess_jail(
        self,
        code: str,
        env: Optional[Dict[str, str]] = None,
        workspace: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs the code in a localized jail subdirectory with environment stripping."""
        temp_dir = workspace or tempfile.mkdtemp(prefix="edith_jail_")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Verify script path is not blocked
        script_path = os.path.join(temp_dir, "jail_script.py")
        if is_path_blocked(temp_dir) or is_path_blocked(script_path):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Access denied: workspace or script path matches security blocklist.",
                "duration": 0.0,
                "mode": "subprocess_jail"
            }

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Clear standard system environment to prevent leakage of credentials/API keys
        safe_env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": temp_dir,
            "PYTHONUNBUFFERED": "1"
        }
        
        if env:
            for k, v in env.items():
                if not is_path_blocked(k) and not is_path_blocked(v):
                    safe_env[k] = v

        t0 = time.time()
        try:
            proc = subprocess.run(
                ["python", "jail_script.py"],
                cwd=temp_dir,
                env=safe_env,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            duration = time.time() - t0
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "duration": duration,
                "mode": "subprocess_jail"
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Process timed out after {self.timeout}s.",
                "duration": self.timeout,
                "mode": "subprocess_jail"
            }
        finally:
            # Only clean up if we created the temp dir ourselves
            if not workspace:
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass
