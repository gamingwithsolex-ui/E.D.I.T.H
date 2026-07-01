"""
edith/core/agents/orchestrator.py
Orchestrator agent for decomposing complex tasks and delegating them to sub-agents.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List, Optional, Callable
from edith.core.agents.base import BaseAgent
from edith.core.agents.react import EdithReActAgent
from edith.core.agents.codeact import EdithCodeActAgent

class EdithOrchestratorAgent(BaseAgent):
    """Orchestrates multi-agent tasks by breaking requests down and executing sub-agents."""

    def __init__(
        self,
        client,
        model: str,
        support_client=None,
        emit_debug: Optional[Callable[[str], None]] = None
    ) -> None:
        super().__init__(client, model, emit_debug=emit_debug)
        self.support_client = support_client

    def run(self, user_input: str, context: Optional[str] = None) -> str:
        self.on_turn_start(user_input)
        
        self._dbg("Generating execution plan...")
        plan_prompt = (
            "You are E.D.I.T.H., a master orchestrator agent.\n"
            "Analyze the user request and decompose it into a structured, step-by-step plan.\n"
            "Output a JSON object with the key 'plan' containing a list of sub-tasks. Each task must specify:\n"
            "  - 'id': integer id\n"
            "  - 'desc': description of the sub-task\n"
            "  - 'agent_type': 'codeact' for data/coding/math/analysis, or 'react' for general tool/system actions.\n\n"
            "Do NOT output any markdown fences, reasoning text, or extra characters. Output raw JSON only.\n\n"
            f"User request: {user_input}"
        )
        
        raw_plan = self.call_llm([{"role": "user", "content": plan_prompt}], temperature=0.15)
        # Strip code fences if the model generated them despite instructions
        clean_plan = raw_plan.replace("```json", "").replace("```", "").strip()
        
        try:
            plan_data = json.loads(clean_plan)
            plan = plan_data.get("plan", [])
        except Exception as e:
            self._dbg(f"Plan JSON parse error: {e}. Raw plan: {raw_plan}")
            # Fallback plan: run as react directly
            plan = [{"id": 1, "desc": user_input, "agent_type": "react"}]
            
        self._dbg(f"Plan generated with {len(plan)} subtasks.")
        
        task_outcomes = []
        for task in plan:
            tid = task.get("id")
            desc = task.get("desc")
            agent_type = task.get("agent_type", "react")
            
            self._dbg(f"Executing Subtask {tid}: '{desc}' using {agent_type} agent...")
            
            # Instantiate sub-agent
            if agent_type == "codeact":
                agent = EdithCodeActAgent(
                    self.client, 
                    self.model, 
                    emit_debug=self._emit_debug_fn
                )
            else:
                agent = EdithReActAgent(
                    self.client, 
                    self.model, 
                    emit_debug=self._emit_debug_fn
                )
                
            task_context = f"Full request context: {user_input}\nContext from previous steps:\n" + "\n".join(task_outcomes)
            outcome = agent.run(desc, context=task_context)
            task_outcomes.append(f"Subtask {tid} result: {outcome}")
            
        self._dbg("Synthesizing final answer...")
        synthesis_prompt = (
            "You are E.D.I.T.H., compiling the final response for the user.\n"
            f"Original user request: {user_input}\n\n"
            "Sub-tasks completed:\n" + "\n".join(task_outcomes) + "\n\n"
            "Based on the outcomes above, synthesize a complete, elegant and cohesive answer for the user. "
            "Address them directly and keep it concise and spoken-friendly."
        )
        
        final_answer = self.call_llm([{"role": "user", "content": synthesis_prompt}])
        self.on_turn_end(final_answer)
        return final_answer
