"""
ProgramPlanner (Plan & Execute Agent): Breaks request into steps, decides learning objective and conversation structure.
"""
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm


class ProgramPlanner:
    def __init__(self):
        pass

    def run(self, prompt: str, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (plan with learning_objective, conversation_structure), steps for logging."""
        system = "You are a language-learning planner. Output only valid JSON with keys: learning_objective (string), conversation_structure (list of step names)."
        user = f"User request: {prompt}. Output JSON only."
        response, full = call_llm(system, user, "ProgramPlanner")
        steps = [{"module": "ProgramPlanner", "prompt": {"system": system, "user": user}, "response": full}]
        plan = parse_json_from_llm(response)
        plan.setdefault("learning_objective", "Practice informal conversation.")
        plan.setdefault("conversation_structure", ["greeting", "topic", "close"])
        return plan, steps
