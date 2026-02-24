"""
ProgramPlanner (Plan & Execute Agent): Breaks request into steps, decides learning objective and conversation structure.
"""
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section, cefr_label


class ProgramPlanner:
    def __init__(self):
        pass

    def run(self, prompt: str, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (plan with learning_objective, conversation_structure, key_vocabulary), steps for logging."""
        user_profile = context.get("user_profile") or {}
        scenario = context.get("scenario") or ""
        conversation_history = context.get("conversation_history") or []
        
        # Extract user info
        name = (user_profile.get("name") or "Learner").strip()
        level = (user_profile.get("level") or "B1").strip()
        goals = (user_profile.get("goals") or "").strip()
        
        # Build recent conversation context
        recent_history = ""
        if conversation_history:
            last_3 = conversation_history[-6:]  # Last 3 exchanges
            recent_history = "\n".join([f"{m.get('role', '')}: {m.get('content', '')}" for m in last_3])
        
        # Enhanced system prompt
        system = (
            "You are an expert language learning planner specializing in casual and daily conversation practice. \n\n"
            "Think through the following steps:\n"
            "1. Analyze the learner's level and goals\n"
            "2. Identify key skills to practice in this scenario\n"
            "3. Plan conversation phases that build naturally\n"
            "4. Determine difficulty adjustments for the learner's level\n\n"
            "Output ONLY valid JSON with these exact keys:\n"
            "- learning_objective: 1-2 sentences describing what the learner will practice (specific skills, vocabulary, grammar)\n"
            "- conversation_structure: list of 4-5 conversation phases (e.g. 'greeting', 'introduce interests', 'discuss topic', 'swap roles', 'wrap-up')\n"
            "- key_vocabulary: list of 5-7 words or phrases relevant to this scenario\n"
            "- difficulty_adjustments: brief guidance on adapting to the user's level\n"
            "Focus on authentic, modern daily speech patterns. "
            "At the end, add: ANSWER: {json output}"
        )
        
        # Build detailed user prompt with context
        user = (
            f"Learner Profile:\n"
            f"- Name: {name}\n"
            f"- Level: {cefr_label(level)}\n"
            f"- Interests: {goals if goals else '(not specified)'}\n\n"
            f"Scenario: {scenario if scenario else prompt}\n\n"
            f"User request: {prompt}\n\n"
        )
        
        if recent_history:
            user += f"Recent conversation:\n{recent_history}\n\n"
        
        user += (
            "Plan a structured, engaging conversation practice session tailored to this learner's level and interests. "
            "Think through each element step by step."
            "At the end, extract your final answer as ANSWER: {json output}"
        )
        
        response, full = call_llm(system, user, "ProgramPlanner")
        steps = [{"module": "ProgramPlanner", "prompt": {"system": system, "user": user}, "response": full}]
        # Extract only the ANSWER section, discarding reasoning steps
        answer_only = extract_answer_section(response)
        plan = parse_json_from_llm(answer_only)
        
        # Defaults with enhanced structure
        plan.setdefault("learning_objective", f"Practice {scenario or prompt} using authentic daily speech appropriate for {level} level.")
        plan.setdefault("conversation_structure", ["greeting", "explore interests", "discuss topic", "exchange perspective", "friendly close"])
        plan.setdefault("key_vocabulary", ["daily", "informal", "casual"])
        plan.setdefault("difficulty_adjustments", f"Adapt to {cefr_label(level)}: use vocabulary and grammar complexity appropriate for this level.")
        
        return plan, steps
