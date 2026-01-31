"""
UserEvaluation (ReAct Agent): Interacts during conversation, adapts difficulty, updates proficiency, produces summary.
"""
import json
from typing import Any

from .llm_helper import call_llm


class UserEvaluation:
    def __init__(self):
        pass

    def run(self, user_message: str, scenario: dict, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (reply, updated_proficiency, summary_if_finished), steps for logging."""
        history = context.get("conversation_history", [])
        history_str = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in history[-6:]])
        level = (context.get("user_profile") or {}).get("level", "B1")

        system = "You are a language practice partner. Use informal slang. Match the user's level. Output only valid JSON with keys: reply (string), summary (null or string, only if conversation should end). Keep reply short."
        user = f"Scenario: {scenario.get('scenario','')}. User level: {level}. History:\n{history_str}\nUser: {user_message}. Output JSON only."
        response, full = call_llm(system, user, "UserEvaluation")
        steps = [{"module": "UserEvaluation", "prompt": {"system": system, "user": user}, "response": full}]

        try:
            out = json.loads(response) if response.strip().startswith("{") else {}
        except json.JSONDecodeError:
            out = {}
        out.setdefault("reply", "Sounds good! Keep going.")
        out.setdefault("summary", None)
        return out, steps
