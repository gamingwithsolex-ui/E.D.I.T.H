"""
edith/core/agents/react.py
JSON-based ReAct agent for tool execution.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional, Callable
from edith.core.agents.base import BaseAgent
from edith.config import AGENT_MAX_STEPS, AGENT_CONFIRM_DESTRUCTIVE
from edith.tools.executor import TOOL_REGISTRY, execute_tool, is_destructive_shell
from edith.core.personality import build_agent_system_prompt

_TOOL_CALL_RE = re.compile(
    r"TOOL_CALL_START\s*(\{.*?\})\s*TOOL_CALL_END",
    re.DOTALL,
)
_FINAL_ANSWER_RE = re.compile(
    r"FINAL_ANSWER\s*\n(.*)",
    re.DOTALL | re.IGNORECASE,
)

class EdithReActAgent(BaseAgent):
    """ReAct agent loop executing standard JSON tool calls."""

    def _extract_tool_call(self, text: str):
        m = _TOOL_CALL_RE.search(text)
        if not m:
            return None, None
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
            tool = data.get("tool", "").strip()
            args = data.get("args", {})
            return tool, args
        except json.JSONDecodeError as e:
            self._dbg(f"JSON parse error in tool call: {e}")
            return None, None

    def _extract_final_answer(self, text: str):
        m = _FINAL_ANSWER_RE.search(text)
        if m:
            return m.group(1).strip()
        return None

    def run(self, user_input: str, context: Optional[str] = None) -> str:
        self.on_turn_start(user_input)
        
        system_prompt = build_agent_system_prompt(context or "")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_input},
        ]
        
        observations = []
        
        for step in range(1, AGENT_MAX_STEPS + 1):
            self._dbg(f"Step {step}/{AGENT_MAX_STEPS}")
            raw_reply = self.call_llm(messages, temperature=0.2)
            
            if not raw_reply:
                self._dbg("Empty reply from planner — aborting")
                break
                
            final = self._extract_final_answer(raw_reply)
            if final:
                self.on_turn_end(final)
                return final
                
            tool_name, args = self._extract_tool_call(raw_reply)
            if not tool_name:
                self._dbg("No tool call detected — treating as final answer")
                self.on_turn_end(raw_reply)
                return raw_reply.strip()
                
            self.on_tool_call(tool_name, args)
            
            # Guard destructive commands
            _, is_destructive = TOOL_REGISTRY.get(tool_name, (None, False))
            if tool_name == "run_shell" and is_destructive_shell(args.get("cmd", "")):
                is_destructive = True
                
            if is_destructive and AGENT_CONFIRM_DESTRUCTIVE:
                confirm_msg = (
                    f"I'm about to perform a potentially destructive action: **{tool_name}**\n"
                    f"Details: `{json.dumps(args)[:200]}`\n\n"
                    f"Please confirm to proceed."
                )
                self.on_turn_end(confirm_msg, error=True)
                return confirm_msg
                
            # Execute tool
            result, _ = execute_tool(tool_name, args)
            obs_snippet = result[:300]
            self._dbg(f"Observation snippet: {obs_snippet}")
            
            messages.append({"role": "assistant", "content": raw_reply})
            messages.append({"role": "user", "content": f"OBSERVATION:\n{result[:2000]}\n\nContinue. Output FINAL_ANSWER if done."})
            
        summary_msg = "ReAct loop reached maximum steps limit."
        self.on_turn_end(summary_msg, error=True)
        return summary_msg
