"""
UserEvaluation (ReAct Agent): Interacts during conversation, adapts difficulty, updates proficiency, produces summary.
"""
import json
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm


class UserEvaluation:
    def __init__(self):
        pass

    def run(self, user_message: str, scenario: dict, context: dict[str, Any]) -> tuple[dict, list[dict]]:
        """Returns (reply, updated_proficiency, summary_if_finished), steps for logging."""
        history = context.get("conversation_history", [])
        history_str = "\n".join([f"{m.get('role','')}: {m.get('content','')}" for m in history[-6:]])
        level = (context.get("user_profile") or {}).get("level", "B1")
        dialogue_seed = scenario.get("dialogue_seed") or []
        rag_examples = scenario.get("rag_examples") or []

        # Inject real Reddit-style examples so the model replies in that style
        examples_block = ""
        if rag_examples:
            examples_block = "Example phrases from real informal conversations (reply in this style, 1-2 short sentences):\n" + "\n".join(f"- {ex}" for ex in rag_examples[:5]) + "\n\n"
        seed_block = f"Possible opening lines for this scenario: {dialogue_seed}.\n\n" if dialogue_seed else ""

        system = "You are a casual language practice partner. Reply with informal, natural slang like in the examples. Match the user's level. Output only valid JSON with keys: reply (string), summary (null or string only if conversation should end). Keep reply to 1-2 short sentences, varied and specific to what the user said."
        user = f"Scenario: {scenario.get('scenario','')}. User level: {level}.\n{examples_block}{seed_block}History:\n{history_str}\nUser: {user_message}\n\nRespond in the same informal style as the examples. Output JSON only."
        response, full = call_llm(system, user, "UserEvaluation")
        steps = [{"module": "UserEvaluation", "prompt": {"system": system, "user": user}, "response": full}]

        out = parse_json_from_llm(response)
        # Fallback only when reply is missing or empty - use context-aware defaults, NEVER repeat dialogue_seed
        reply = (out.get("reply") or "").strip()
        if not reply:
            # Varied replies that acknowledge the user instead of repeating an opening line
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
