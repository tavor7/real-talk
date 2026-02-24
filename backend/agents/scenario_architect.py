"""
ScenarioArchitect: Builds realistic scenarios from RAG + user profile; pre-decided scenarios for fast start.
"""
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section, truncate_if_needed, cefr_label
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
        
        # Use rephrased RAG query from supervisor if available, otherwise build one
        rephrased_rag_query = context.get("rephrased_rag_query")
        if rephrased_rag_query:
            rag_query = rephrased_rag_query
        else:
            # Fallback: build RAG query locally if supervisor didn't rephrase it
            rag_query = _build_rag_query(hint, user_profile, context)
        print(f"ScenarioArchitect: Using RAG query: '{rag_query}'")
        # RAG: retrieve using the optimized query
        chunks = retrieve(rag_query, top_k=1, use_cache=True)
        rag_texts = [truncate_if_needed(c.get("text", "").strip()) for c in chunks if c.get("text")]
        rag_context = "\n".join(rag_texts) if rag_texts else ""

        # Extract user profile and plan details
        name = (user_profile.get("name") or "the learner").strip()
        level = (user_profile.get("level") or "B1").strip()
        goals_str = (user_profile.get("goals") or "").strip()
        profile_brief = f"Learner: {name}, level {cefr_label(level)}" + (f", into {goals_str}" if goals_str else "")
        
        # Get plan details
        learning_objective = plan.get("learning_objective", "practice informal conversation")
        conversation_structure = plan.get("conversation_structure", [])
        key_vocabulary = plan.get("key_vocabulary", [])
        difficulty_adjustments = plan.get("difficulty_adjustments", "")
        
        # Enhanced system prompt focused on scenario only
        system = (
            "You are an expert scenario designer for authentic language practice. \n\n"
            "Think through the following steps:\n"
            "1. Understand the learning objective and what skills should be practiced\n"
            "2. Analyze the conversation structure and key vocabulary needed\n"
            "3. Review authentic examples from the RAG corpus\n"
            "4. Design a SPECIFIC setting that naturally incorporates the learning focus\n"
            "5. Describe it with authentic, casual daily speech.\n\n"
            "Output ONLY valid JSON with this exact key:\n"
            "- scenario: 2-3 sentences describing the SPECIFIC setting and context for this conversation\n\n"
            "The scenario must be SPECIFIC to the learning objective, not generic. "
            "Describe the setting and conversational context clearly. "
            "At the end, add: ANSWER: {json output}"
        )
        
        # Build detailed prompt with full context
        plan_for_llm = truncate_if_needed(learning_objective)
        rag_for_llm = truncate_if_needed(rag_context)
        structure_str = ", ".join(conversation_structure[:5]) if conversation_structure else "greeting, topic, exchange, close"
        vocab_str = ", ".join(key_vocabulary[:5]) if key_vocabulary else "casual speech"
        
        user_for_llm = (
            f"Learner profile: {profile_brief}\n"
            f"Learning Objective: {plan_for_llm}\n"
            f"Conversation Structure: {structure_str}\n"
            f"Retrieved examples of authentic speech you can use to design the scenario:\n{rag_for_llm}\n\n"
            f"Design a SPECIFIC, engaging scenario for this conversation. "
            f"Think through the learning objective and authentic examples. "
            f"think step by step, at the end, write your final scenario as ANSWER: {{json with 'scenario' key only}}"
        )

        # For logging: always store full prompt so user sees everything
        user_full = (
            f"Learner profile: {profile_brief}\n"
            f"Learning Objective: {learning_objective}\n"
            f"Conversation Structure: {', '.join(conversation_structure) if conversation_structure else 'natural flow'}\n"
            f"Retrieved examples of authentic speech:\n{rag_context}\n\n"
            f"Design a SPECIFIC, engaging scenario for this conversation. "
            f"Think through the learning objective and authentic examples. "
            f"Focus on the setting and context."
            f"At the end, extract your final answer as ANSWER: {{json with 'scenario' key only}}"
        )
        
        response, full = call_llm(system, user_for_llm, "ScenarioArchitect")
        steps.append({
            "module": "ScenarioArchitect",
            "prompt": {"system": system, "user": user_full},
            "response": full
        })

        # Extract only the ANSWER section, discarding reasoning steps
        answer_only = extract_answer_section(response)
        out = parse_json_from_llm(answer_only)
        
        # Smarter fallback scenario based on actual learning objective
        fallback_scenario = f"Scenario: {hint}. Learning focus: {learning_objective}. Have a natural conversation in this context using authentic daily speech."
        
        out.setdefault("scenario", fallback_scenario)
        
        # Pass RAG examples to ConversationPartner so replies use real informal style
        out["rag_examples"] = rag_texts[:5]
        return out, steps
