"""
ScenarioArchitect: Builds realistic scenarios from RAG + user profile; pre-decided scenarios for fast start.
"""
import json
from typing import Any

from .llm_helper import call_llm
from rag.reddit_retriever import retrieve


# Pre-decided scenarios for fast start (no LLM needed when user picks one)
PREDEFINED_SCENARIOS = [
    {"id": "coffee", "name": "Casual chat at a coffee shop", "hint": "coffee shop small talk slang"},
    {"id": "gaming", "name": "Arguing about a game with a friend", "hint": "gaming slang argument"},
    {"id": "party", "name": "Meeting someone at a party", "hint": "party introduction slang"},
    {"id": "streaming", "name": "Talking like a streamer to viewers", "hint": "streaming slang viewers"},
    {"id": "diner", "name": "Ordering food at a casual diner", "hint": "ordering food casual slang"},
]


class ScenarioArchitect:
    def __init__(self):
        pass

    def run(self, plan: dict, user_profile: dict, scenario_hint: str | None, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (scenario with dialogue_seed), steps for logging."""
        steps = []
        hint = scenario_hint or "casual informal conversation"
        # RAG: retrieve Reddit chunks (cached)
        chunks = retrieve(hint, top_k=3, use_cache=True)
        rag_context = "\n".join([c.get("text", "")[:200] for c in chunks]) if chunks else ""

        system = "You are a scenario builder for language practice. Output only valid JSON with keys: scenario (string), dialogue_seed (list of 2-3 opening lines). Use informal slang. Keep it short."
        user = f"Plan: {plan.get('learning_objective', '')}. User level: {user_profile.get('level', 'B1')}. RAG context:\n{rag_context[:500]}\nHint: {hint}. Output JSON only."
        response, full = call_llm(system, user, "ScenarioArchitect")
        steps.append({"module": "ScenarioArchitect", "prompt": {"system": system, "user": user}, "response": full})

        try:
            out = json.loads(response) if response.strip().startswith("{") else {}
        except json.JSONDecodeError:
            out = {}
        out.setdefault("scenario", "Casual chat")
        out.setdefault("dialogue_seed", ["Hey! What's up?", "Not much, you?"])
        return out, steps
