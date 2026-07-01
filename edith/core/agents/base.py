"""
edith/core/agents/base.py
Abstract base class defining the interface for Edith agents.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable

class BaseAgent(ABC):
    """Base class for all Edith specialized agents."""

    def __init__(
        self,
        client,
        model: str,
        tools: Optional[List[str]] = None,
        emit_debug: Optional[Callable[[str], None]] = None
    ) -> None:
        self.client = client
        self.model = model
        self.tools = tools or []
        self._emit_debug_fn = emit_debug

    def _dbg(self, msg: str) -> None:
        print(f"[AGENT:{self.__class__.__name__}] {msg}")
        if self._emit_debug_fn:
            self._emit_debug_fn(msg)

    def call_llm(self, messages: list, max_tokens: int = 1500, temperature: float = 0.2) -> str:
        """Call LLM client supporting fallback chain when quota/rate limits are hit."""
        import edith.core.brain as _brain
        from edith.core.state import state
        
        # Helper to process and log successful responses
        def process_response(resp, model_name):
            content = resp.choices[0].message.content
            if not content:
                content = getattr(resp.choices[0].message, "reasoning_content", "") or ""
            content = content.strip()
            if content:
                state.active_model = model_name
                return content
            return ""

        # ==========================================
        # OFFLINE MODE ROUTING
        # ==========================================
        if not state.is_online:
            self._dbg("System is OFFLINE. Routing directly to Local Brain.")
            if hasattr(_brain, "client_local") and _brain.client_local:
                try:
                    resp = _brain.client_local.chat.completions.create(
                        model=_brain.LOCAL_MODEL_NAME,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    return process_response(resp, "OLLAMA (OFFLINE)")
                except Exception as e:
                    self._dbg(f"Local AI offline routing failed: {e}")
            return ""

        # ==========================================
        # ONLINE MODE ROUTING
        # ==========================================
        network_timed_out = False
        
        # 1. Primary Client
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=8.0,
            )
            res = process_response(resp, self.model)
            if res: return res
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "connect" in err_str:
                network_timed_out = True
                self._dbg(f"Network Timeout on '{self.model}'. Skipping cloud fallbacks.")
            else:
                self._dbg(f"Model '{self.model}' failed: {e}. Trying fallback...")
                    
        # 2. Fallback to OpenRouter
        if _brain.client_openrouter and not network_timed_out:
            self._dbg("Falling back to OpenRouter...")
            for model in ["google/gemini-2.5-flash", "deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"]:
                try:
                    resp = _brain.client_openrouter.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=8.0,
                    )
                    res = process_response(resp, model)
                    if res: return res
                except Exception as e:
                    err_str = str(e).lower()
                    if "timeout" in err_str or "connect" in err_str:
                        network_timed_out = True
                        self._dbg(f"Network Timeout on OpenRouter. Skipping cloud fallbacks.")
                        break
                    self._dbg(f"OpenRouter model '{model}' failed: {e}. Trying next OpenRouter fallback...")
                    continue

        # 3. Fallback to DeepSeek V4 Pro on Nvidia NIM
        if _brain.client_support and not network_timed_out:
            self._dbg(f"Falling back to DeepSeek V4 Pro ({_brain.MODEL_SUPPORT})...")
            try:
                resp = _brain.client_support.chat.completions.create(
                    model=_brain.MODEL_SUPPORT,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=8.0,
                )
                res = process_response(resp, "DEEPSEEK V4 (NIM)")
                if res: return res
            except Exception as e:
                err_str = str(e).lower()
                if "timeout" in err_str or "connect" in err_str:
                    network_timed_out = True
                self._dbg(f"DeepSeek V4 fallback failed: {e}")
                
        # 4. Final Fallback to Ollama
        if hasattr(_brain, "client_local") and _brain.client_local:
            self._dbg("Falling back to Ollama (Local Brain)...")
            try:
                resp = _brain.client_local.chat.completions.create(
                    model=_brain.LOCAL_MODEL_NAME,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                res = process_response(resp, "OLLAMA (LOCAL)")
                if res: return res
            except Exception as e:
                self._dbg(f"Ollama local fallback failed: {e}")

        self._dbg("All models in LLM client chain failed.")
        return ""

    # Event handlers/hooks for voice assistant feedback
    def on_turn_start(self, user_input: str) -> None:
        self._dbg(f"Started turn for query: {user_input[:60]}...")

    def on_tool_call(self, tool_name: str, args: Dict[str, Any]) -> None:
        self._dbg(f"Invoking tool: {tool_name}")

    def on_turn_end(self, result: str, error: bool = False) -> None:
        self._dbg(f"Finished turn. Result size: {len(result)} chars (error={error})")

    @abstractmethod
    def run(self, user_input: str, context: Optional[str] = None) -> str:
        """Run the agent turn loop and return final spoken response."""
        pass
