"""
edith/core/agents/codeact.py
Python CodeAct execution agent.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Callable
from edith.core.agents.base import BaseAgent
from edith.sandbox.runner import SandboxRunner
from edith.config import AGENT_MAX_STEPS

# Extract ```python ... ``` block
_CODE_BLOCK_RE = re.compile(r"```python\s*(.*?)\s*```", re.DOTALL)

class EdithCodeActAgent(BaseAgent):
    """CodeAct agent that writes and runs python code in a sandbox to complete tasks."""

    def __init__(
        self,
        client,
        model: str,
        sandbox_timeout: int = 30,
        use_docker: bool = False,
        emit_debug: Optional[Callable[[str], None]] = None
    ) -> None:
        super().__init__(client, model, emit_debug=emit_debug)
        self.sandbox = SandboxRunner(timeout=sandbox_timeout, use_docker=use_docker)

    def run(self, user_input: str, context: Optional[str] = None) -> str:
        self.on_turn_start(user_input)
        
        system_prompt = (
            "You are E.D.I.T.H., a premium CodeAct-style executor agent.\n"
            "Instead of calling pre-defined tools, you write and execute Python code in an isolated sandbox "
            "to perform operations (e.g. read/write files, analyze data, solve math, search paths, etc.).\n\n"
            "INSTRUCTIONS:\n"
            "1. Output your reasoning first, followed by a SINGLE Python block enclosed in ```python ... ```.\n"
            "2. The code's stdout/stderr will be returned to you as the next observation.\n"
            "3. Use standard print() statements to display findings or results.\n"
            "4. Repeat writing code blocks until the goal is fully met.\n"
            "5. When done, output a conversational response explaining your results without any code blocks.\n\n"
            f"CONTEXT:\n{context or ''}"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_input},
        ]
        
        for step in range(1, AGENT_MAX_STEPS + 1):
            self._dbg(f"Step {step}/{AGENT_MAX_STEPS}")
            reply = self.call_llm(messages, max_tokens=2000, temperature=0.1)
            
            if not reply:
                break
                
            code_match = _CODE_BLOCK_RE.search(reply)
            if not code_match:
                # No code block generated — the model is done and returning the final response
                self.on_turn_end(reply)
                return reply
                
            code_content = code_match.group(1).strip()
            self.on_tool_call("python_sandbox", {"code": code_content[:150] + "..."})
            
            # Execute code in sandbox
            res = self.sandbox.run_python_code(code_content)
            
            stdout = res.get("stdout", "").strip()
            stderr = res.get("stderr", "").strip()
            success = res.get("success", False)
            
            obs = f"STDOUT:\n{stdout}\n"
            if stderr:
                obs += f"STDERR:\n{stderr}\n"
            obs += f"STATUS: {'SUCCESS' if success else 'FAILED'}"
            
            self._dbg(f"Execution duration: {res.get('duration', 0.0):.2f}s")
            
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": f"OBSERVATION:\n{obs}\n\nProceed to next step."})
            
        final_err = "CodeAct execution reached maximum step limits without a final response."
        self.on_turn_end(final_err, error=True)
        return final_err
