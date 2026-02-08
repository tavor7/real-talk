"""
UserEvaluation (ReAct Agent): Interacts during conversation, adapts difficulty, updates proficiency, produces summary.
"""
import json
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm

# CEFR level definitions so the LLM knows what each level means (vocabulary, grammar, length)
CEFR_LEVELS_HELP = (
    "CEFR levels: A1=beginner (very simple words, present tense, short phrases). "
    "A2=elementary (simple everyday language, basic past/future). "
    "B1=intermediate (main points, familiar topics, simple connected text). "
    "B2=upper intermediate (standard speech, detailed text, some idiom). "
    "C1=advanced (fluent, idiom and nuance). C2=proficient (near-native, subtlety)."
)


def _level_instruction(level: str) -> str:
    """Return instruction so the LLM adapts reply difficulty to the learner's CEFR level."""
    level = (level or "B1").upper()
    if level in ("A1", "A2"):
        return "Use simple words and short sentences so an A1/A2 learner can follow; avoid rare idioms."
    if level in ("B1", "B2"):
        return "Use everyday informal language and common slang; B1/B2 can handle normal conversation."
    if level in ("C1", "C2"):
        return "You can use richer idiom and nuance; C1/C2 learners can handle native-like informal speech."
    return "Match your reply to the learner's level: simpler for A1/A2, normal for B1/B2, richer for C1/C2."


def generate_end_conversation(
    profile: dict[str, Any],
    conversation_history: list[dict],
    scenario_name: str,
) -> tuple[str, str, str]:
    """Generate a sign-off, practice summary, and short instructions for the next conversation.
    Returns (reply, summary, llm_instructions). Summary = 2–3 tips. llm_instructions = 1–2 sentences for the next talk.
    """
    level = profile.get("level", "B1")
    goals = (profile.get("goals") or "").strip()
    name = profile.get("name", "the learner")
    history_str = "\n".join(
        f"{m.get('role', '')}: {m.get('content', '')}" for m in conversation_history[-8:]
    )
    system = (
        "You are a language practice partner. The learner has chosen to end the conversation. "
        "Output only valid JSON with keys: reply (string), summary (string), llm_instructions (string). "
        "reply = one short friendly sign-off (e.g. 'Nice chatting! Catch you next time.'). "
        "summary = 2–3 concrete suggestions for how to improve and what to practice until the next session or in daily life. Use bullet points or short lines. "
        "llm_instructions = 1–2 short sentences for the next conversation with this learner (e.g. 'Learner practiced coffee shop small talk; next time encourage longer answers or introduce new vocabulary.'). Base on what was practiced and their level."
    )
    user = (
        f"Learner: {name}, level {level}, goals: {goals}. Scenario was: {scenario_name}.\n\n"
        f"Conversation so far:\n{history_str}\n\n"
        f"Generate reply, summary, and llm_instructions. Output JSON only."
    )
    response, _ = call_llm(system, user, "UserEvaluation")
    out = parse_json_from_llm(response)
    reply = (out.get("reply") or "Nice chatting! See you next time.").strip()
    summary = (out.get("summary") or "").strip()
    if not summary:
        summary = (
            f"Until next time: try using what you practiced in real chats or when {goals or 'practicing'}."
        )
    llm_instructions = (out.get("llm_instructions") or "").strip()
    return reply, summary, llm_instructions


class UserEvaluation:
    def __init__(self):
        pass

    def run(self, user_message: str, scenario: dict, context: dict[str, Any], *, is_first_turn: bool = False) -> tuple[dict, list[dict]]:
        """Returns (reply, updated_proficiency, summary_if_finished), steps for logging."""
        history = context.get("conversation_history", [])
        history_str = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in history[-12:]])
        profile = context.get("user_profile") or {}
        level = profile.get("level", "B1")
        goals = profile.get("goals", "")
        name = profile.get("name", "the learner")
        dialogue_seed = scenario.get("dialogue_seed") or []
        rag_examples = scenario.get("rag_examples") or []
        profile_ctx = (context.get("profile_conversation_context") or "").strip()

        examples_block = ""
        if rag_examples:
            examples_block = "Example informal style (use similar tone):\n" + "\n".join(f"- {ex}" for ex in rag_examples[:5]) + "\n\n"
        seed_block = f"Possible openings: {dialogue_seed}.\n\n" if dialogue_seed else ""
        previous_block = f"Previous sessions / instructions for this conversation:\n{profile_ctx}\n\n" if profile_ctx else ""

        scenario_name = scenario.get("scenario", "")
        level_instruction = _level_instruction(level)

        if is_first_turn:
            system = (
                "You are a conversation partner talking TO the learner (not as the learner). "
                "The learner is practicing AS the chosen profile (e.g. Alex, A2 level, into gaming/streaming). "
                "You are someone in the scenario having a casual conversation with them. "
                "Output only valid JSON with keys: reply (string), summary (null). "
                "Your reply must be ONE short opening line that STARTS the conversation — say the first thing you say TO the learner. "
                "Do NOT say 'I'm Alex' or speak AS the learner. You are talking TO them. "
                "Do NOT ask 'what do you want to practice' — that breaks the scene. "
                "Just start a natural, casual conversation based on the scenario."
            )
            user = (
                f"{previous_block}"
                f"{CEFR_LEVELS_HELP}\n\n"
                f"Scenario: {scenario_name}. Learner practicing AS: {name}, level {level}, interests: {goals}. {level_instruction}\n\n"
                f"You are someone in this scenario having a casual conversation with {name}. Write the FIRST line you say TO them to start the conversation. "
                f"Use their name and/or interests when natural. Use informal slang. You are talking TO them, not AS them. "
                f"Just have a natural chat based on the scenario — don't act like a service provider unless the scenario specifically calls for it.\n\n"
                f"{examples_block}{seed_block}Output JSON only: {{\"reply\": \"...\", \"summary\": null}}."
            )
        else:
            end_instructions = (
                "If the user is saying goodbye or the conversation is wrapping up: put a short friendly sign-off in reply and 1-2 sentences of practice tip in summary. Otherwise leave summary as null."
            )
            system = (
                "You are a conversation partner talking TO the learner (not as the learner). "
                "The learner is practicing AS the chosen profile (e.g. Alex, A2 level). "
                "You are someone in the scenario having a casual conversation with them. "
                "CRITICAL: You are NOT the learner. Do NOT speak AS the learner or say what the learner would say. "
                "You are having a natural conversation — respond as yourself, not as a service provider unless the scenario specifically requires it. "
                "Your reply must directly respond to the user's last message and continue the natural flow of the conversation. "
                "Key principles: "
                "1. Stay on the same topic as the user's message — do not change subjects unless they do. "
                "2. Acknowledge what the user said — if they stated a preference, opinion, or fact, acknowledge it before adding your own. "
                "3. When the user asks 'and you?' or 'what about you?', answer in the same context they asked (e.g. if they asked about drinks, say what you like to drink; if they asked about plans, say what you'll do). "
                "4. Keep replies natural and conversational — match the learner's level, use informal slang, and keep it to 1-2 short sentences. "
                "5. Remember: You are talking TO the learner. The learner speaks AS themselves. Have a natural conversation, not a transaction. "
                "Output only valid JSON: reply (string), summary (null or string). " + end_instructions
            )
            user = (
                f"{previous_block}"
                f"User's last message: \"{user_message}\"\n\n"
                f"You are someone in this scenario having a casual conversation with {name}. "
                f"The learner ({name}) is practicing AS this profile. You are NOT the learner. "
                f"Continue the conversation naturally. Stay on the same topic. If they asked 'and you?' or 'what about you?', answer in the same context. "
                f"Acknowledge what they said before adding your own response. "
                f"Have a natural chat — don't act like a service provider unless the scenario specifically calls for it.\n\n"
                f"Setting: {scenario_name}. Learner: {name}, level {level}. {level_instruction}\n\n"
                f"{examples_block}"
                f"Dialogue so far:\n{history_str}\n\n"
                f"Reply to the user's message as yourself talking TO the learner. Do NOT speak as the learner. Output JSON only."
            )
        response, full = call_llm(system, user, "UserEvaluation")
        steps = [{"module": "UserEvaluation", "prompt": {"system": system, "user": user}, "response": full}]

        out = parse_json_from_llm(response)
        # Fallback only when reply is missing or empty - use context-aware defaults, NEVER repeat dialogue_seed
        reply = (out.get("reply") or "").strip()
        # Never use a meta "what do you want to practice?" as first message — replace with in-scenario opener
        # Never let agent speak AS the learner (e.g. "I'm Alex") — agent talks TO the learner
        if is_first_turn and reply:
            meta_phrases = ("what do you want to practice", "what would you like to practice", "what do you wanna practice", "what would you like to practice today")
            if any(p in reply.lower() for p in meta_phrases):
                reply = ""
            # Check if agent is speaking AS the learner (wrong)
            if name and (f"i'm {name.lower()}" in reply.lower() or f"i am {name.lower()}" in reply.lower() or reply.lower().startswith(f"{name.lower()}:") or reply.lower().startswith(f"i'm {name.lower()}")):
                reply = ""
        if not reply:
            if is_first_turn:
                # Opening line fallback: tie to scenario and profile, use name when we have it
                s = (scenario_name or "").lower()
                g = (goals or "").lower()
                n = (name or "").strip()
                if "coffee" in s or "shop" in s:
                    if n and ("stream" in g or "game" in g):
                        reply = f"Hey {n}! Grabbing a coffee before your stream? What game are you playing?"
                    else:
                        reply = f"Hey{n and ' ' + n}! What can I get you today?" if n else "Hey! What can I get you?"
                elif "game" in s or "gaming" in g:
                    reply = f"Yo{n and ' ' + n}! You catch that stream last night? So good." if n else "Yo! You catch that stream last night?"
                elif "stream" in g or "streaming" in s:
                    reply = f"What's up{n and ' ' + n}! You stream or just watch?" if n else "What's up! You stream or just watch?"
                else:
                    reply = f"Hey{n and ' ' + n}! What's up?" if n else "Hey! What's up?"
            else:
                um = (user_message or "").lower()
                if any(w in um for w in ("how are you", "how're you", "how r u", "you?")):
                    reply = "I'm good, thanks! How about you?"
                elif any(w in um for w in ("hello", "hi", "hey")):
                    reply = "Hey! What's up?"
                elif any(w in um for w in ("good", "great", "fine")):
                    reply = "Nice! So what's going on?"
                else:
                    reply = "Yeah, same here! What do you wanna talk about?"
        out["reply"] = reply
        out.setdefault("summary", None)
        return out, steps
