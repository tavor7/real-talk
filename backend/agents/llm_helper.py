"""
Minimal LLM helper: one function to call OpenAI when key is set, else return mock.
Optimized to minimize LLM calls and stay within budget.
"""
import os
import json
import re
import time
from typing import Any


def truncate_if_needed(text: str, default_max: int | None = None) -> str:
    """Truncate text only if LLM_PROMPT_MAX_LENGTH env var is set. Otherwise return full text.
    If env var is set, use that limit. If not set and default_max is provided, use default_max.
    """
    max_len_str = os.environ.get("LLM_PROMPT_MAX_LENGTH", "").strip()
    if max_len_str:
        try:
            max_len = int(max_len_str)
            return text[:max_len] if len(text) > max_len else text
        except ValueError:
            pass
    if default_max is not None:
        return text[:default_max] if len(text) > default_max else text
    return text


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


def _extract_content(r: Any) -> str:
    """Extract message content from OpenAI-compatible response; some providers use different shapes."""
    # Response may be a dict (e.g. from some proxies or custom clients)
    if isinstance(r, dict):
        choices = r.get("choices") or []
        if not choices:
            return ""
        choice = choices[0]
        msg = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)
        if isinstance(msg, dict):
            content = msg.get("content") or msg.get("text")
            if content and str(content).strip():
                return str(content).strip()
        if isinstance(choice, dict):
            content = choice.get("content") or choice.get("text")
            if content and str(content).strip():
                return str(content).strip()
        return ""

    if not r or not getattr(r, "choices", None) or not r.choices:
        return ""
    choice = r.choices[0]
    msg = getattr(choice, "message", None)
    # Standard: choices[0].message.content
    if msg is not None:
        content = getattr(msg, "content", None)
        if content is not None and str(content).strip():
            return str(content).strip()
        if hasattr(msg, "model_dump"):
            d = msg.model_dump()
            content = d.get("content") or d.get("text")
            if content and str(content).strip():
                return str(content).strip()
        if isinstance(msg, dict):
            content = msg.get("content") or msg.get("text")
            if content and str(content).strip():
                return str(content).strip()
    # Some providers: choices[0].text
    text = getattr(choice, "text", None)
    if text is not None and str(text).strip():
        return str(text).strip()
    return ""


def call_llm(system: str, user: str, module: str) -> tuple[str, str]:
    """
    Call LLM (OpenAI chat). Returns (response_text, full_response_for_logging).
    If no API key or API returns empty, uses mock so the app keeps working.
    """
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if api_key:
        try:
            from openai import OpenAI
            base_url = (os.environ.get("OPENAI_BASE_URL") or "").strip() or None
            client = OpenAI(api_key=api_key, base_url=base_url)
            def do_request():
                # max_tokens: use env var if set, else None (no limit, use model default)
                max_tokens_str = os.environ.get("LLM_MAX_TOKENS", "").strip()
                max_tokens = int(max_tokens_str) if max_tokens_str else None
                kwargs = {
                    "model": (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip(),
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                }
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens
                return client.chat.completions.create(**kwargs)

            # Space out requests so provider rate limit doesn't return empty (e.g. llmod.ai)
            # ScenarioArchitect and SystemCritic often get empty (2nd and 4th calls), so extra delay
            if module == "ScenarioArchitect":
                delay = 1.2
                retry_delay = 1.5
            elif module == "SystemCritic":
                delay = 1.0
                retry_delay = 1.5
            else:
                delay = 0.5
                retry_delay = 1.0
            time.sleep(delay)
            r = do_request()
            text = _extract_content(r)
            # Retry up to 2 times if empty (rate limit or transient failure)
            for _ in range(2):
                if text:
                    break
                time.sleep(retry_delay)
                r = do_request()
                text = _extract_content(r)
            if not text:
                if os.environ.get("DEBUG_LLM"):
                    try:
                        import sys
                        raw = getattr(r, "model_dump", lambda: None)() if hasattr(r, "model_dump") else str(r)
                        print(f"[DEBUG_LLM] {module} raw response: {raw[:800]}", file=sys.stderr)
                    except Exception:
                        pass
                fallback = _mock_response(module, "API returned empty content")
                return fallback, f"(LLM returned empty; fallback used)\n\n{fallback}"
            return text, text
        except Exception as e:
            mock = _mock_response(module, str(e))
            return mock, mock
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
