"""
SystemCritic (Reflection Agent): Reviews dialogue, ensures slang authenticity, safety, clarity, level; decides when to finish.
"""
import json
from typing import Any

from .llm_helper import call_llm, truncate_if_needed


class SystemCritic:
    def __init__(self):
        pass

    def run(self, dialogue: list, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (review result, should_finish), steps for logging. Assesses only the learner (user), not the agent."""
        last = dialogue[-4:] if len(dialogue) > 4 else dialogue
        # Build full versions for logging
        dialogue_str_full = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in last])
        learner_only_full = "\n".join([m.get("content", "") for m in last if m.get("role") == "user"])
        # Truncate only if LLM_PROMPT_MAX_LENGTH env var is set
        dialogue_str_for_llm = truncate_if_needed(dialogue_str_full)
        learner_only_for_llm = truncate_if_needed(learner_only_full)
        level = (context.get("user_profile") or {}).get("level", "B1")
        system = (
            "You are a dialogue reviewer. Assess ONLY the LEARNER (user) messages — not the assistant. "
            "Output only valid JSON: approved (bool), should_finish (bool), feedback (string). "
            "feedback = comment on learner's language (safety, clarity, level appropriateness)."
        )
        user_for_llm = (
            f"Level: {level}. Learner messages: {learner_only_for_llm or '(none)'}\n"
            f"Full dialogue (for context only):\n{dialogue_str_for_llm}\n\n"
            f"Is the learner's participation appropriate for this level? Output JSON only."
        )
        user_full = (
            f"Level: {level}. Learner messages: {learner_only_full or '(none)'}\n"
            f"Full dialogue (for context only):\n{dialogue_str_full}\n\n"
            f"Is the learner's participation appropriate for this level? Output JSON only."
        )
        response, full = call_llm(system, user_for_llm, "SystemCritic")
        steps = [{"module": "SystemCritic", "prompt": {"system": system, "user": user_full}, "response": full}]
        try:
            out = json.loads(response) if response.strip().startswith("{") else {}
        except json.JSONDecodeError:
            out = {}
        out.setdefault("approved", True)
        out.setdefault("should_finish", False)
        out.setdefault("feedback", "OK")
        return out, steps
