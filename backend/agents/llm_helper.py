"""
Minimal LLM helper: one function to call OpenAI when key is set, else return mock.
Optimized to minimize LLM calls and stay within budget.
"""
import os
import json
import re
from typing import Any


def parse_json_from_llm(response: str) -> dict:
    """Extract JSON from LLM response (handles ```json ... ``` or raw {...})."""
    text = (response or "").strip()
    for pattern in (r"```(?:json)?\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```"):
        m = re.search(pattern, text)
        if m:
            text = m.group(1).strip()
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return {}


def call_llm(system: str, user: str, module: str) -> tuple[str, str]:
    """
    Call LLM (OpenAI chat). Returns (response_text, full_response_for_logging).
    If no API key, returns mock based on module.
    """
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if api_key:
        try:
            from openai import OpenAI
            base_url = (os.environ.get("OPENAI_BASE_URL") or "").strip() or None
            client = OpenAI(api_key=api_key, base_url=base_url)
            r = client.chat.completions.create(
                model=(os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip(),
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=500,
            )
            text = (r.choices[0].message.content or "").strip()
            return text, text
        except Exception as e:
            return _mock_response(module, str(e)), _mock_response(module, str(e))
    return _mock_response(module, None), _mock_response(module, None)


def _mock_response(module: str, err: str | None) -> str:
    """Sensible mock so app runs without API key."""
    mocks = {
        "ProgramPlanner": json.dumps({"learning_objective": "Practice informal slang in a casual scenario.", "conversation_structure": ["greeting", "topic", "follow-up", "close"]}),
        "ScenarioArchitect": json.dumps({"scenario": "Casual chat at a coffee shop", "dialogue_seed": ["Hey! What's up?", "Not much, just grabbing coffee."]}),
        "UserEvaluation": json.dumps({"reply": "Hey! That's cool. What do you want to practice today?", "summary": None}),
        "SystemCritic": json.dumps({"approved": True, "should_finish": False, "feedback": "Level and slang appropriateness OK."}),
        "SupervisorAgent": "Plan created. Scenario ready. You can start the conversation.",
    }
    if err:
        return (mocks.get(module) or mocks["SupervisorAgent"]) + f" [LLM error: {err}]"
    return mocks.get(module) or mocks["SupervisorAgent"]
