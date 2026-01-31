"""
ProgramPlanner (Plan & Execute Agent): Breaks request into steps, decides learning objective and conversation structure.
"""
import json
from typing import Any

from .llm_helper import call_llm


class ProgramPlanner:
    def __init__(self):
        pass

    def run(self, prompt: str, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (plan with learning_objective, conversation_structure), steps for logging."""
        system = "You are a language-learning planner. Output only valid JSON with keys: learning_objective (string), conversation_structure (list of step names)."
        user = f"User request: {prompt}. Output JSON only."
        response, full = call_llm(system, user, "ProgramPlanner")
        steps = [{"module": "ProgramPlanner", "prompt": {"system": system, "user": user}, "response": full}]
        try:
            plan = json.loads(response) if response.strip().startswith("{") else {}
        except json.JSONDecodeError:
            plan = {"learning_objective": "Practice informal conversation.", "conversation_structure": ["greeting", "topic", "close"]}
        plan.setdefault("learning_objective", "Practice informal conversation.")
        plan.setdefault("conversation_structure", ["greeting", "topic", "close"])
        return plan, steps
