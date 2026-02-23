"""
Critic (Reflection Agent): From the second turn onward, when the Supervisor decides to invoke it
(e.g. user said goodbye or conversation diverged from scenario), the Critic decides whether to
end the conversation or to continue with feedback for the Supervisor/ConversationPartner.
"""
from typing import Any

from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section, truncate_if_needed


class SystemCritic:
    """Decides whether to end the conversation or continue with feedback."""

    def __init__(self):
        pass

    def run(
        self,
        scenario_description: str,
        conversation_history: list[dict],
        last_user_message: str,
        context: dict[str, Any],
    ) -> tuple[dict, list[dict]]:
        """Decide: end conversation or continue with feedback.

        Returns (result_dict, steps) where result_dict has:
          - end_conversation: bool — if True, supervisor should end and call UserEvaluation
          - feedback: str — when end_conversation is False, guidance for ConversationPartner
        """
        history_str = "\n".join(
            f"{m.get('role', '')}: {m.get('content', '')}" for m in conversation_history[-8:]
        )
        scenario_for_llm = truncate_if_needed(scenario_description or "Casual conversation")
        history_for_llm = truncate_if_needed(history_str)
        last_msg_for_llm = truncate_if_needed(last_user_message or "")

        system = (
            "You are a dialogue reviewer for a language-learning conversation. "
            "Your job is to decide whether this conversation should END now or CONTINUE.\n\n"
            "Output ONLY valid JSON with these exact keys:\n"
            "- end_conversation (boolean): true if the conversation should end now, false to continue.\n"
            "- feedback (string): When end_conversation is false, give 1-2 sentences of guidance for the conversation partner (e.g. steer back to scenario, acknowledge user's intent). When end_conversation is true, you may leave feedback empty or add a brief reason.\n\n"
            "Set end_conversation to TRUE when: the user clearly wants to end (e.g. goodbye, bye, see you, I have to go, let's stop, that's it for me), or the conversation has naturally reached a closing point.\n"
            "Set end_conversation to FALSE when: the user is still engaged; then use feedback to guide the partner (e.g. 'User went off-topic; gently bring the conversation back to the scenario.' or 'User said something that could be a farewell but might be casual; continue the conversation and see if they add more.').\n"
            "At the end, add: ANSWER: {json output}"
        )
        user = (
            f"Scenario (what this conversation is supposed to be about):\n{scenario_for_llm}\n\n"
            f"Recent conversation:\n{history_for_llm}\n\n"
            f"Last user message: \"{last_msg_for_llm}\"\n\n"
            "Should the conversation end now, or continue? If continue, what feedback should the conversation partner use? "
            "Think step by step, then output your final JSON. At the end, extract: ANSWER: {\"end_conversation\": ..., \"feedback\": \"...\"}"
        )
        user_full = (
            f"Scenario (what this conversation is supposed to be about):\n{scenario_description or 'Casual conversation'}\n\n"
            f"Recent conversation:\n{history_str}\n\n"
            f"Last user message: \"{last_user_message}\"\n\n"
            "Should the conversation end now, or continue? If continue, what feedback should the conversation partner use?"
        )

        response, full = call_llm(system, user, "SystemCritic")
        steps = [{"module": "SystemCritic", "prompt": {"system": system, "user": user_full}, "response": full}]

        answer_only = extract_answer_section(response)
        out = parse_json_from_llm(answer_only)

        out.setdefault("end_conversation", False)
        out.setdefault("feedback", "")

        return out, steps
