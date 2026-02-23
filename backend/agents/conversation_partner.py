"""
ConversationPartner: Generates natural conversational responses based on scenario and RAG examples.
Talks TO the learner as a conversation partner in the scenario.
"""
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section


def _level_instruction(level: str) -> str:
    """Return instruction so the LLM adapts reply difficulty to the learner's CEFR level."""
    level = (level or "B1").upper()
    if level in ("A1", "A2"):
        return "Use simple words and short sentences; avoid rare idioms."
    if level in ("B1", "B2"):
        return "Use everyday informal language and common slang."
    if level in ("C1", "C2"):
        return "You can use richer idiom and nuance; use native-like informal speech."
    return "Match your reply to the learner's level."


class ConversationPartner:
    """Generates natural conversational responses as a partner in the scenario."""

    def __init__(self):
        pass

    def run(self, user_message: str, scenario: dict, context: dict[str, Any], *, is_first_turn: bool = False) -> tuple[dict, list[dict]]:
        """Generate conversational response based on scenario and user input.
        Returns (reply_dict, steps) where reply_dict has 'reply' key."""
        history = context.get("conversation_history", [])
        history_str = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in history[-6:]])
        profile = context.get("user_profile") or {}
        level = profile.get("level", "B1")
        rag_examples = scenario.get("rag_examples") or []

        examples_block = ""
        if rag_examples:
            examples_block = "Example authentic style (use similar tone):\n" + "\n".join(f"- {ex}" for ex in rag_examples[:5]) + "\n\n"

        scenario_name = scenario.get("scenario", "")
        level_instruction = _level_instruction(level)

        # Build rich scenario context from ALL available scenario details
        scenario_context = f"Scenario: {scenario_name}"
        # Include all scenario fields for complete context
        for key, value in scenario.items():
            if key not in ("scenario", "rag_examples") and value:
                # Format the key nicely (convert snake_case to Title Case)
                formatted_key = key.replace("_", " ").title()
                if isinstance(value, (list, dict)):
                    scenario_context += f"\n{formatted_key}: {str(value)[:200]}"
                else:
                    scenario_context += f"\n{formatted_key}: {value}"

        if is_first_turn:
            system = (
                "You are a conversation partner in a casual scenario. \n\n"
                "Think through these steps:\n"
                "1. Understand the scenario setting\n"
                "2. Consider how to naturally OPEN the conversation\n"
                "3. Choose an opening that matches the level and setting\n"
                "4. Use informal, authentic slang\n\n"
                "Output only valid JSON with key: reply (string). "
                "Your reply must be ONE short opening line that STARTS the conversation naturally. "
                "At the end, add: ANSWER: {json output}"
            )
            user = (
                f"Language level instruction: {level_instruction}\n\n"
                f"{scenario_context}\n\n"
                f"Start a natural conversation in this scenario. Write the FIRST line you say. "
                f"Think step by step about how to open naturally. "
                f"{examples_block}At the end, extract: ANSWER: {{\"reply\": \"...\"}}"
            )
        else:
            system = (
                "You are a conversation partner having a casual conversation. \n\n"
                "Think through these steps:\n"
                "1. READ the user's message carefully\n"
                "2. IDENTIFY the topic or intent (question, statement, opinion, etc.)\n"
                "3. CHOOSE how to respond (answer question, acknowledge opinion, build on statement)\n"
                "4. CRAFT a natural, casual 1-2 sentence reply using informal slang\n"
                "5. STAY in scenario context\n\n"
                "CRITICAL RULES: "
                "- YOUR RESPONSE MUST directly address what the user said\n"
                "- Do NOT give a generic response\n"
                "- If they ask a question, answer it. If they share opinion, acknowledge it. If they make statement, respond to it.\n"
                "- Keep replies natural, casual, and 1-2 short sentences\n"
                "- Stay in character for the scenario\n\n"
                "Output only valid JSON: {\"reply\": \"...\"} "
                "At the end, add: ANSWER: {json output}"
            )
            user = (
                f"Language level instruction: {level_instruction}\n\n"
                f"{scenario_context}\n\n"
                f"***RESPOND TO THIS MESSAGE:*** \"{user_message}\"\n\n"
                f"This is what the user just said. Your job is to respond naturally to EXACTLY this message while staying in the scenario context.\n\n"
                f"Context (previous conversation):\n{history_str}\n\n"
                f"{examples_block}"
                f"Think step by step: What did they say? How should you respond? "
                f"NOW write your natural response to the user's message above. Stay on their topic. "
                f"Acknowledge what they said, then respond. Keep it natural and casual. Stay in character for the scenario.\n\n"
                f"At the end, extract: ANSWER: {{\"reply\": \"...\"}}"
            )

        response, full = call_llm(system, user, "ConversationPartner")
        steps = [{"module": "ConversationPartner", "prompt": {"system": system, "user": user}, "response": full}]

        # Extract only the ANSWER section, discarding reasoning steps
        answer_only = extract_answer_section(response)
        out = parse_json_from_llm(answer_only)
        reply = (out.get("reply") or "").strip()

        # Fallback logic - simple scenario-based responses
        if not reply:
            if is_first_turn:
                s = (scenario_name or "").lower()
                if "coffee" in s or "shop" in s:
                    reply = "Hey! What can I get you?"
                elif "game" in s or "gaming" in s:
                    reply = "Yo! You into gaming?"
                elif "stream" in s or "streaming" in s:
                    reply = "What's up! You stream?"
                else:
                    reply = "Hey! What's up?"
            else:
                um = (user_message or "").lower()
                if any(w in um for w in ("how are you", "how're you", "how r u", "you?")):
                    reply = "I'm good! How about you?"
                elif any(w in um for w in ("hello", "hi", "hey")):
                    reply = "Hey! What's up?"
                elif any(w in um for w in ("good", "great", "fine")):
                    reply = "Nice! So what's going on?"
                else:
                    reply = "Yeah, same here!"

        return {"reply": reply}, steps
