"""
ScenarioArchitect: Builds realistic scenarios from RAG + user profile; pre-decided scenarios for fast start.
"""
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm, truncate_if_needed
from rag.reddit_retriever import retrieve


# Pre-decided scenarios for fast start (no LLM needed when user picks one)
PREDEFINED_SCENARIOS = [
    {"id": "coffee", "name": "Casual chat at a coffee shop", "hint": "coffee shop small talk slang"},
    {"id": "gaming", "name": "Arguing about a game with a friend", "hint": "gaming slang argument"},
    {"id": "party", "name": "Meeting someone at a party", "hint": "party introduction slang"},
    {"id": "streaming", "name": "Talking like a streamer to viewers", "hint": "streaming slang viewers"},
    {"id": "diner", "name": "Ordering food at a casual diner", "hint": "ordering food casual slang"},
]


def _build_rag_query(scenario_hint: str, user_profile: dict, context: dict[str, Any]) -> str:
    """Build RAG query from scenario + user info + recent conversation so retrieval is relevant to all."""
    parts = [scenario_hint or "casual informal conversation"]
    goals = (user_profile.get("goals") or "").strip()
    if goals:
        parts.append(goals)
    history = context.get("conversation_history") or []
    if history:
        # Last 2–4 messages (1–2 turns) to capture current topic (e.g. coffee, tea, gaming)
        recent = history[-4:]
        topic_bits = [truncate_if_needed(str(m.get("content", "")).strip()) for m in recent if m.get("content")]
        if topic_bits:
            parts.append(" ".join(topic_bits))
    return " ".join(p for p in parts if p).strip() or "casual informal conversation"


class ScenarioArchitect:
    def __init__(self):
        pass

    def run(self, plan: dict, user_profile: dict, scenario_hint: str | None, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (scenario with dialogue_seed), steps for logging."""
        steps = []
        hint = scenario_hint or "casual informal conversation"
        # RAG: retrieve by scenario + user goals + recent conversation (relevant to current topic)
        rag_query = _build_rag_query(hint, user_profile, context)
        chunks = retrieve(rag_query, top_k=5, use_cache=True)
        rag_texts = [_truncate_if_needed(c.get("text", "").strip()) for c in chunks if c.get("text")]
        rag_context = "\n".join(rag_texts) if rag_texts else ""

        # Scenario text should include the learner's profile so the UI shows a personalized brief
        name = (user_profile.get("name") or "the learner").strip()
        level = (user_profile.get("level") or "B1").strip()
        goals_str = (user_profile.get("goals") or "").strip()
        profile_brief = f"Learner: {name}, level {level}" + (f", into {goals_str}" if goals_str else "")
        system = (
            "You are a scenario builder for language practice. Output only valid JSON with keys: scenario (string), dialogue_seed (list of 2-3 opening lines). "
            "scenario = 1-2 sentences describing the setting. The learner is practicing AS the chosen profile (e.g. Alex, A2 level, into gaming/streaming). "
            "The agent will talk TO the learner (e.g. as a barista, friend, etc.). Example: 'You're practicing as Alex at a coffee shop. Practice ordering drinks, small talk about gaming/streaming, and casual conversation.' "
            "Use informal slang. Keep it short."
        )
        plan_full = plan.get("learning_objective") or ""
        # Truncate only if LLM_PROMPT_MAX_LENGTH env var is set
        plan_for_llm = truncate_if_needed(plan_full)
        rag_for_llm = truncate_if_needed(rag_context)
        user_for_llm = f"{profile_brief}. Hint: {hint}. Plan: {plan_for_llm}. RAG: {rag_for_llm}\nOutput JSON: scenario (describe setting; learner practices AS this profile; agent talks TO learner), dialogue_seed (2-3 example opening lines the AGENT might say TO the learner)."
        # For logging: always store full prompt so user sees everything
        user_full = f"{profile_brief}. Hint: {hint}. Plan: {plan_full}. RAG: {rag_context}\nOutput JSON: scenario (describe setting; learner practices AS this profile; agent talks TO learner), dialogue_seed (2-3 example opening lines the AGENT might say TO the learner)."
        response, full = call_llm(system, user_for_llm, "ScenarioArchitect")
        steps.append({"module": "ScenarioArchitect", "prompt": {"system": system, "user": user_full, "rag_query": rag_query}, "response": full})

        out = parse_json_from_llm(response)
        # Fallback scenario: clarify that learner practices AS the profile, agent talks TO them
        fallback_scenario = f"Practice as {name} (level {level}" + (f", into {goals_str}" if goals_str else "") + f") in a casual scenario. The agent will talk to you."
        out.setdefault("scenario", fallback_scenario)
        out.setdefault("dialogue_seed", [f"Hey {name}! What's up?" if name else "Hey! What's up?", "Not much, you?"])
        # Pass RAG examples to UserEvaluation so replies use real informal style
        out["rag_examples"] = rag_texts[:5]
        return out, steps
