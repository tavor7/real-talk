"""
UserEvaluation: Evaluates user performance at end of conversation and generates summary.
Evaluation and feedback are based solely on the learner's (user's) messages, not the assistant's.
"""
import json
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section

# Short CEFR level descriptions shown at the start of the end-of-conversation summary
CEFR_LEVEL_DESCRIPTIONS = {
    "A1": "Beginner — You can understand and use familiar everyday expressions and very basic phrases.",
    "A2": "Elementary — You can communicate in simple, routine tasks and describe in simple terms aspects of your life.",
    "B1": "Intermediate — You can deal with most situations while traveling and describe experiences, events, and give reasons.",
    "B2": "Upper intermediate — You can interact with fluency and discuss familiar topics in some depth.",
    "C1": "Advanced — You can use language flexibly and produce clear, well-structured text on complex subjects.",
    "C2": "Proficient — You can understand virtually everything and express yourself spontaneously and precisely.",
}


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
    level = (profile.get("level") or "B1").strip().upper()
    name = profile.get("name", "the learner")

    # Extract ONLY the learner's (user's) messages — do not pass assistant/agent messages at all
    user_messages = [m for m in conversation_history if m.get("role") == "user"]
    # Label every line as LEARNER so the model cannot confuse any message with the assistant's
    user_messages_str = "\n".join(
        f"[LEARNER] {m.get('content', '')}" for m in user_messages[-8:]
    )

    system = (
        "You are an expert in real-life, daily English communication. You will receive messages that are ALL from the LEARNER (the user). "
        "Every message is prefixed with [LEARNER]. There are NO assistant or other speaker messages in the input.\n\n"
        "CRITICAL: Evaluate ONLY the learner. Focus on REAL-LIFE and DAILY ENGLISH, not just grammar and phrasing.\n\n"
        "Assess in terms of:\n"
        "- How natural and everyday they sound (would this work in a real café, with friends, at work, online?)\n"
        "- Whether they would be understood and could get their point across in daily situations\n"
        "- Use of everyday expressions, informal tone, and how appropriate it is for the situation\n"
        "- Confidence and clarity in real-world contexts (ordering, chatting, reacting, asking for things)\n"
        "- Mention grammar or wording only when it would actually confuse someone or sound odd in real life; otherwise focus on communicativeness and naturalness.\n\n"
        "Output only valid JSON with keys: sign_off (string), evaluation (string), llm_instructions (string). "
        "sign_off = one short friendly sign-off. "
        "evaluation = 2–4 short paragraphs about how they did in REAL-LIFE terms: what worked well in daily communication, what would help them sound more natural or be clearer in everyday situations, and one or two concrete tips for real conversations (not a grammar list). "
        "llm_instructions = 1-2 sentences for the next conversation (e.g. focus on reacting naturally, or on everyday phrases for X). "
        "At the end, add: ANSWER: {json output}"
    )

    user = (
        f"Learner's stated level: {level}\n"
        f"Scenario (for context only): {scenario_name}\n\n"
        f"--- LEARNER'S MESSAGES ONLY (every line below is from the learner) ---\n\n"
        f"{user_messages_str}\n\n"
        f"--- END OF LEARNER MESSAGES ---\n\n"
        f"Evaluate their REAL-LIFE, daily English: how natural and clear they'd be in everyday situations. Base feedback only on the [LEARNER] messages above. Output JSON. ANSWER: {{json}}"
    )
    
    response, _ = call_llm(system, user, "UserEvaluation")
    # Extract only the ANSWER section, discarding reasoning steps
    answer_only = extract_answer_section(response)
    out = parse_json_from_llm(answer_only)
    
    sign_off = (out.get("sign_off") or "Good job! Chat later!").strip()
    evaluation = (out.get("evaluation") or "").strip()
    if not evaluation:
        evaluation = "Keep practicing everyday English in real-life style conversations; focus on sounding natural and getting your point across."

    # Prepend the user's level and its short description at the beginning of the summary
    level_desc = CEFR_LEVEL_DESCRIPTIONS.get(level, CEFR_LEVEL_DESCRIPTIONS.get("B1", ""))
    evaluation = f"Your level: {level} — {level_desc}\n\n{evaluation}"

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

