"""
UserEvaluation: Evaluates user performance at end of conversation and generates summary.
"""
import json
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section


def evaluate_user_performance(
    profile: dict[str, Any],
    conversation_history: list[dict],
    scenario_name: str,
) -> tuple[str, str, str]:
    """Evaluate user's English performance based on conversation.
    Returns (sign_off, evaluation, llm_instructions).
    - sign_off: friendly closing message
    - evaluation: assessment of user's English level, strengths, and areas to work on
    - llm_instructions: guidance for next conversation with this learner
    """
    level = profile.get("level", "B1")
    name = profile.get("name", "the learner")
    
    # Extract ONLY user messages from conversation history
    user_messages = [m for m in conversation_history if m.get("role") == "user"]
    # Get last 8 user messages for context
    user_messages_str = "\n".join(
        f"User: {m.get('content', '')}" for m in user_messages[-8:]
    )
    
    system = (
        "You are an expert English language evaluator. Analyze the learner's conversation performance step by step. "
        "\n\nThink through the following steps:\n"
        "1. Analyze each user message for grammar, vocabulary, and proficiency level\n"
        "2. Identify strengths (what they did well)\n"
        "3. Identify specific areas to improve with concrete examples\n"
        "4. Summarize overall proficiency level\n"
        "5. Determine focus areas for next conversation\n"
        "\nThen output only valid JSON with keys: sign_off (string), evaluation (string), llm_instructions (string). "
        "sign_off = one short friendly sign-off (e.g. 'Good job! Chat later!'). "
        "evaluation = detailed assessment covering: current English proficiency level, grammar and vocabulary use, strengths demonstrated, specific areas to improve (e.g., 'Work on present perfect tense', 'Use more varied vocabulary'), and specific mistakes to avoid. Focus on concrete English skills, not practice advice. "
        "llm_instructions = 1-2 short sentences for the next conversation (e.g. 'Focus on past tense; user struggled with 'did' vs 'was doing'.'). "
        "At the end, add: ANSWER: {json output}"
    )
    
    user = (
        f"Current level: {level}\n"
        f"Scenario: {scenario_name}\n\n"
        f"User's messages:\n{user_messages_str}\n\n"
        f"Evaluate this learner's English performance based ONLY on their messages. Think through each message step by step. "
        f"Be specific about what they did well and what they need to improve. At the end, extract your final answer as ANSWER: {{json}}"
    )
    
    response, _ = call_llm(system, user, "UserEvaluation")
    # Extract only the ANSWER section, discarding reasoning steps
    answer_only = extract_answer_section(response)
    out = parse_json_from_llm(answer_only)
    
    sign_off = (out.get("sign_off") or "Good job! Chat later!").strip()
    evaluation = (out.get("evaluation") or "").strip()
    if not evaluation:
        evaluation = f"Continue working on your English. Practice more conversation exchanges in this scenario."
    
    llm_instructions = (out.get("llm_instructions") or "").strip()
    if not llm_instructions:
        llm_instructions = f"Learner at {level} level in {scenario_name}. Focus on natural conversation flow next time."
    
    return sign_off, evaluation, llm_instructions


# Legacy function name for backward compatibility
def generate_end_conversation(
    profile: dict[str, Any],
    conversation_history: list[dict],
    scenario_name: str,
) -> tuple[str, str, str]:
    """Backward compatible wrapper. Calls evaluate_user_performance."""
    return evaluate_user_performance(profile, conversation_history, scenario_name)


class UserEvaluation:
    """Evaluates user performance after conversation ends."""

    def __init__(self):
        pass

    def evaluate(self, profile: dict[str, Any], conversation_history: list[dict], scenario_name: str) -> tuple[dict, list[dict]]:
        """Evaluate user and generate feedback.
        Returns (evaluation_dict, steps) where evaluation_dict has 'sign_off', 'evaluation', 'llm_instructions' keys."""
        sign_off, evaluation, llm_instructions = evaluate_user_performance(profile, conversation_history, scenario_name)
        
        step = {
            "module": "UserEvaluation",
            "prompt": {"task": "evaluate_user_performance", "scenario": scenario_name},
            "response": {"sign_off": sign_off, "evaluation": evaluation, "llm_instructions": llm_instructions}
        }
        
        return {
            "sign_off": sign_off,
            "evaluation": evaluation,
            "llm_instructions": llm_instructions
        }, [step]

