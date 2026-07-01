"""
edith/tools/mcp_client.py
Model Context Protocol client implementation for Edith.
Connects to external tool providers (servers) via Stdio or SSE transport protocols.
"""
from __future__ import annotations
import json
import itertools
import subprocess
import shutil
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# Protocol Constants
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

@dataclass
class MCPRequest:
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int | str] = 0
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        obj = {"jsonrpc": self.jsonrpc, "method": self.method, "params": self.params}
        if self.id is not None:
            obj["id"] = self.id
        return obj

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

@dataclass
class MCPResponse:
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    id: int | str = 0
    jsonrpc: str = "2.0"

    @classmethod
    def from_json(cls, data: str) -> MCPResponse:
        parsed = json.loads(data)
        return cls(
            result=parsed.get("result"),
            error=parsed.get("error"),
            id=parsed.get("id", 0),
            jsonrpc=parsed.get("jsonrpc", "2.0"),
        )

class MCPError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code = code
        self.message = message
        self.data = data

    def __str__(self) -> str:
        return f"MCPError({self.code}): {self.message}"

# Transport Layer
class MCPTransport(ABC):
    @abstractmethod
    def send(self, request: MCPRequest) -> MCPResponse:
        pass

    @abstractmethod
    def send_notification(self, request: MCPRequest) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

class StdioTransport(MCPTransport):
    """Subprocess stdio communication transport."""
    def __init__(self, command: List[str]) -> None:
        self._command = command
        self._process: Optional[subprocess.Popen[str]] = None
        self._start()

    def _start(self) -> None:
        # If command uses npx on Windows, invoke via shell or absolute paths
        cmd = list(self._command)
        if cmd and cmd[0] == "npx" and shutil.which("npx.cmd"):
            cmd[0] = "npx.cmd"
            
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True if os.name == 'nt' else False
        )

    def send(self, request: MCPRequest) -> MCPResponse:
        proc = self._process
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise RuntimeError("MCP Transport subprocess is not running")

        line = request.to_json() + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        if not response_line:
            # Check if stderr has diagnostic info
            stderr_out = ""
            if proc.stderr:
                try:
                    stderr_out = proc.stderr.read(200)
                except Exception:
                    pass
            raise RuntimeError(f"No response from MCP subprocess. Error: {stderr_out}")
            
        return MCPResponse.from_json(response_line.strip())

    def send_notification(self, request: MCPRequest) -> None:
        proc = self._process
        if proc is None or proc.stdin is None:
            raise RuntimeError("MCP Transport subprocess is not running")
        line = request.to_json() + "\n"
        proc.stdin.write(line)
        proc.stdin.flush()

    def close(self) -> None:
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

class SSETransport(MCPTransport):
    """JSON-RPC over HTTP client supporting Server-Sent Events."""
    def __init__(self, url: str) -> None:
        self._url = url
        self._session_id: Optional[str] = None
        self._client = httpx.Client(timeout=30.0)

    def _build_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id is not None:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _post(self, request: MCPRequest) -> httpx.Response:
        headers = self._build_headers()
        res = self._client.post(self._url, json=request.to_dict(), headers=headers)
        res.raise_for_status()
        new_session_id = res.headers.get("mcp-session-id")
        if new_session_id is not None:
            self._session_id = new_session_id
        return res

    def _extract_sse_data(self, text: str) -> str:
        last_data = ""
        for line in text.splitlines():
            if line.startswith("data:"):
                last_data = line[len("data:") :].strip()
        if not last_data:
            raise RuntimeError("SSE response contained no 'data:' payload.")
        return last_data

    def send(self, request: MCPRequest) -> MCPResponse:
        res = self._post(request)
        content_type = res.headers.get("content-type", "")
        body = res.text
        if "text/event-stream" in content_type or body.lstrip().startswith("event:"):
            body = self._extract_sse_data(body)
        return MCPResponse.from_json(body)

    def send_notification(self, request: MCPRequest) -> None:
        self._post(request)

    def close(self) -> None:
        self._client.close()

# MCP Client Core
class MCPClient:
    """Client that communicates with an MCP server via a transport."""
    def __init__(self, transport: MCPTransport) -> None:
        self._transport = transport
        self._initialized = False
        self._capabilities: Dict[str, Any] = {}
        self._id_counter = itertools.count(1)

    def _next_id(self) -> int:
        return next(self._id_counter)

    def _send(self, method: str, params: Dict[str, Any] | None = None) -> MCPResponse:
        request = MCPRequest(method=method, params=params or {}, id=self._next_id())
        response = self._transport.send(request)
        if response.error is not None:
            raise MCPError(
                code=response.error.get("code", -1),
                message=response.error.get("message", "Unknown error"),
                data=response.error.get("data")
            )
        return response

    def initialize(self) -> Dict[str, Any]:
        params = {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "edith-mcp-client", "version": "1.0.0"},
        }
        res = self._send("initialize", params)
        self._initialized = True
        self._capabilities = res.result.get("capabilities", {})
        self.notify("notifications/initialized")
        return res.result

    def notify(self, method: str, params: Dict[str, Any] | None = None) -> None:
        request = MCPRequest(method=method, params=params or {}, id=None)
        self._transport.send_notification(request)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools in the MCP Server."""
        res = self._send("tools/list")
        return res.result.get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Execute a tool with arguments."""
        res = self._send("tools/call", {"name": name, "arguments": arguments or {}})
        return res.result

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> MCPClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
