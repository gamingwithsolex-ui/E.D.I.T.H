"""
edith/core/agent.py
E.D.I.T.H. Agentic Task Engine — Routing & Entrypoint

Architectural Routing:
  1. Spawns OrchestratorAgent if query is multi-faceted/planning heavy.
  2. Spawns CodeActAgent if query is coding/data-science/math heavy.
  3. Spawns ReActAgent as fallback/general tool executor.
"""
from __future__ import annotations
import edith.core.brain as _brain
from edith.config import LOCAL_MODEL_NAME
from edith.core.agents.react import EdithReActAgent
from edith.core.agents.codeact import EdithCodeActAgent
from edith.core.agents.orchestrator import EdithOrchestratorAgent

def run_agent_task(
    user_input: str,
    memory,
    emit_debug=None,
) -> str:
    """
    Execute a multi-step agentic task routing to the best fit specialized agent.
    """
    _brain.ensure_clients()
    client_local = _brain.client_local
    client_support = _brain.client_support

    if not client_local:
        return "My local neural core is offline — I can't execute agentic tasks right now."

    def _dbg(msg):
        print(f"[AGENT_ROUTER] {msg}")
        if emit_debug:
            emit_debug(f"AGENT_ROUTER: {msg}")

    _dbg(f"Routing task: {user_input[:80]}")

    # Build memory context
    mem_summary = memory.summary(user_input) if memory else ""

    # Simple keyword-based classifier
    query_lower = user_input.lower()
    
    # Check for orchestrator indicators
    orchestrator_keywords = [
        "plan", "steps", "then", "first", "after that", "multiple", "checklist", "orchestrate", "sequence"
    ]
    # Check for codeact/sandbox indicators
    codeact_keywords = [
        "write a python script", "run python", "execute script", "code script", "math", "calculator",
        "calculate", "data analysis", "plot", "graph", "script to", "analyze data"
    ]

    is_orchestrator = any(kw in query_lower for kw in orchestrator_keywords)
    is_codeact = any(kw in query_lower for kw in codeact_keywords)

    # Initialize the selected agent
    if is_orchestrator:
        _dbg("Routing to OrchestratorAgent (multi-step planning)")
        agent = EdithOrchestratorAgent(
            client=client_local,
            model=LOCAL_MODEL_NAME,
            support_client=client_support,
            emit_debug=emit_debug
        )
    elif is_codeact:
        _dbg("Routing to CodeActAgent (isolated Python executor)")
        agent = EdithCodeActAgent(
            client=client_local,
            model=LOCAL_MODEL_NAME,
            emit_debug=emit_debug
        )
    else:
        _dbg("Routing to ReActAgent (general tool execution)")
        agent = EdithReActAgent(
            client=client_local,
            model=LOCAL_MODEL_NAME,
            emit_debug=emit_debug
        )

    # Run agent loop
    try:
        response = agent.run(user_input, context=mem_summary)
        return response
    except Exception as e:
        _dbg(f"Agent execution failed: {e}")
        return f"Error executing task: {e}"
