"""
SystemCritic (Reflection Agent): Reviews dialogue, ensures slang authenticity, safety, clarity, level; decides when to finish.
"""
import json
from typing import Any

from .llm_helper import call_llm


class SystemCritic:
    def __init__(self):
        pass

    def run(self, dialogue: list, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (review result, should_finish), steps for logging."""
        dialogue_str = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in dialogue[-10:]])
        system = "You are a dialogue reviewer. Check: slang authenticity, safety, clarity, level. Output only valid JSON with keys: approved (bool), should_finish (bool), feedback (string)."
        user = f"Dialogue:\n{dialogue_str}. Output JSON only."
        response, full = call_llm(system, user, "SystemCritic")
        steps = [{"module": "SystemCritic", "prompt": {"system": system, "user": user}, "response": full}]
        try:
            out = json.loads(response) if response.strip().startswith("{") else {}
        except json.JSONDecodeError:
            out = {}
        out.setdefault("approved", True)
        out.setdefault("should_finish", False)
        out.setdefault("feedback", "OK")
        return out, steps
