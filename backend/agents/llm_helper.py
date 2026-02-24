"""
Minimal LLM helper: one function to call OpenAI when key is set, else return mock.
Optimized to minimize LLM calls and stay within budget.
"""
import os
import json
import re
import time
from typing import Any


# Short CEFR level descriptions shared across all agents
CEFR_LEVEL_DESCRIPTIONS: dict[str, str] = {
    "A1": "Beginner — can understand and use familiar everyday expressions and very basic phrases.",
    "A2": "Elementary — can communicate in simple, routine tasks and describe basic aspects of daily life.",
    "B1": "Intermediate — can deal with most everyday situations and describe experiences and give reasons.",
    "B2": "Upper-Intermediate — can interact with fluency and discuss familiar topics in some depth.",
    "C1": "Advanced — can use language flexibly and express ideas clearly on complex subjects.",
    "C2": "Proficient — can understand virtually everything and express spontaneously and precisely.",
}


def cefr_label(level: str) -> str:
    """Return a concise label like 'B1 (Intermediate — can deal with most everyday situations...)'."""
    level = (level or "B1").upper().strip()
    desc = CEFR_LEVEL_DESCRIPTIONS.get(level)
    if desc:
        return f"{level} ({desc})"
    return level


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


def extract_answer_section(response: str) -> str:
    """Extract only the part after 'ANSWER:' from LLM response.
    If no ANSWER: found, return the full response."""
    text = (response or "").strip()
    # Look for ANSWER: or answer: (case insensitive)
    import re
    match = re.search(r"(?:ANSWER|answer)\s*:\s*([\s\S]*?)$", text)
    if match:
        return match.group(1).strip()
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
        in_string = False
        escape = False
        quote_char = None
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\" and in_string:
                escape = True
                continue
            if not in_string and (c == '"' or c == "'"):
                in_string = True
                quote_char = c
                continue
            if in_string and c == quote_char:
                in_string = False
                continue
            if not in_string:
                if c == "{":
                    depth += 1
                elif c == "}":
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


def extract_reply_from_llm_response(text: str) -> str:
    """When parse_json_from_llm fails or reply is empty, try to extract reply from raw LLM output.
    Handles malformed JSON and model output that duplicates ANSWER: {\"reply\": \"...\"} inside the reply."""
    if not text or not text.strip():
        return ""
    text = text.strip()
    # Take the last ANSWER: section so we get the actual answer block (model may put reasoning first)
    if " ANSWER:" in text or " answer:" in text.lower():
        match = re.search(r"(?:ANSWER|answer)\s*:\s*([\s\S]*)$", text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()
    # Try to find "reply" : "value" (value can contain escaped quotes \")
    m = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        raw = m.group(1)
        try:
            return json.loads('"' + raw + '"')
        except Exception:
            pass
        return raw.replace('\\"', '"').replace("\\n", "\n").strip()
    # Simpler pattern when value has no internal quotes
    m = re.search(r'"reply"\s*:\s*"([^"]*)"', text)
    if m:
        return m.group(1).strip()
    return ""


def _normalize_content(content: Any) -> str:
    """Turn content into a single string; some APIs return a list of parts (e.g. [{\"type\": \"text\", \"text\": \"...\"}])."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                t = part.get("text") or part.get("content")
                if t:
                    parts.append(str(t))
            else:
                parts.append(str(part))
        return " ".join(parts).strip()
    return str(content).strip()


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
            out = _normalize_content(content)
            if out:
                return out
        if isinstance(choice, dict):
            content = choice.get("content") or choice.get("text")
            out = _normalize_content(content)
            if out:
                return out
        return ""

    if not r or not getattr(r, "choices", None) or not r.choices:
        return ""
    choice = r.choices[0]
    msg = getattr(choice, "message", None)
    if msg is not None:
        content = getattr(msg, "content", None)
        if content is not None:
            out = _normalize_content(content)
            if out:
                return out
        if hasattr(msg, "model_dump"):
            d = msg.model_dump()
            content = d.get("content") or d.get("text")
            out = _normalize_content(content)
            if out:
                return out
        if isinstance(msg, dict):
            content = msg.get("content") or msg.get("text")
            out = _normalize_content(content)
            if out:
                return out
    text = getattr(choice, "text", None)
    if text is not None and str(text).strip():
        return str(text).strip()
    return ""


def call_llm(system: str, user: str, module: str, max_tokens_override: int | None = None) -> tuple[str, str]:
    """
    Call LLM (OpenAI chat). Returns (response_text, full_response_for_logging).
    max_tokens_override: if set, caps output tokens for faster short replies (e.g. 256 for ConversationPartner).
    """
    import sys
    debug_llm = os.environ.get("DEBUG_LLM", "").strip()
    max_tokens = max_tokens_override
    if max_tokens is None:
        mt = os.environ.get("LLM_MAX_TOKENS", "").strip()
        max_tokens = int(mt) if mt else None

    # Print prompt for debugging only if DEBUG_LLM=1
    if debug_llm:
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"[DEBUG] {module} - Prompt sent to LLM:", file=sys.stderr)
        print(f"{'='*80}", file=sys.stderr)
        print(f"System prompt ({len(system)} chars):", file=sys.stderr)
        print(system, file=sys.stderr)
        print(f"\nUser prompt ({len(user)} chars):", file=sys.stderr)
        print(user, file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)
    
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if api_key:
        try:
            from openai import OpenAI
            base_url = (os.environ.get("OPENAI_BASE_URL") or "").strip() or None
            client = OpenAI(api_key=api_key, base_url=base_url)
            def do_request():
                kwargs = {
                    "model": (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip(),
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                }
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens
                return client.chat.completions.create(**kwargs)

            # Optional pre-request delay to avoid provider rate limits (empty content). Set LLM_REQUEST_DELAY=0.2 if you see empty responses.
            delay_str = os.environ.get("LLM_REQUEST_DELAY", "").strip()
            if delay_str:
                try:
                    time.sleep(float(delay_str))
                except ValueError:
                    pass
            retry_delay = 0.6  # seconds when retrying after empty response (rate limit / transient)
            r = do_request()
            text = _extract_content(r)
            # Retry up to 3 times if empty (rate limit or transient failure)
            for retry_num in range(3):
                if text:
                    break
                if debug_llm:
                    print(f"[DEBUG] {module} - Empty response, retrying ({retry_num + 1}/3)...", file=sys.stderr)
                time.sleep(retry_delay)
                r = do_request()
                text = _extract_content(r)
            if not text:
                if debug_llm:
                    try:
                        raw = getattr(r, "model_dump", lambda: None)() if hasattr(r, "model_dump") else str(r)
                        print(f"[DEBUG_LLM] {module} raw response: {raw[:800]}", file=sys.stderr)
                    except Exception:
                        pass
                fallback = _mock_response(module, "API returned empty content")
                if debug_llm:
                    print(f"[DEBUG] {module} - Response: (empty, using fallback)", file=sys.stderr)
                    print(f"{'='*80}\n", file=sys.stderr)
                return fallback, f"(LLM returned empty; fallback used)\n\n{fallback}"
            if debug_llm:
                print(f"[DEBUG] {module} - Response received ({len(text)} chars):", file=sys.stderr)
                print(text, file=sys.stderr)  # Print full response, not truncated
                print(f"{'='*80}\n", file=sys.stderr)
            return text, text
        except Exception as e:
            if debug_llm:
                print(f"[DEBUG] {module} - Exception occurred: {e}", file=sys.stderr)
                print(f"{'='*80}\n", file=sys.stderr)
            mock = _mock_response(module, str(e))
            return mock, mock
    if debug_llm:
        print(f"[DEBUG] {module} - No API key, using mock response", file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)
    return _mock_response(module, None), _mock_response(module, None)


def _mock_response(module: str, err: str | None) -> str:
    """Sensible mock so app runs without API key."""
    mocks = {
        "ProgramPlanner": json.dumps({
            "learning_objective": "Practice informal slang in a casual scenario.",
            "conversation_structure": ["greeting", "topic", "follow-up", "close"],
            "key_vocabulary": ["slang", "informal", "casual"],
            "difficulty_adjustments": "Adapt to learner level"
        }),
        "RAGQueryRephraser": "casual slang conversation authentic dialogue practice",
        "ScenarioArchitect": json.dumps({
            "scenario": "You're at a casual coffee shop having a conversation about everyday topics with slang and informal expressions."
        }),
        "ConversationPartner": json.dumps({
            "reply": "Hey! What's up?"
        }),
        "UserEvaluation": json.dumps({
            "sign_off": "Good job! Chat later!",
            "evaluation": "Your grammar is good overall. Work on using more varied vocabulary and natural expressions. Try to use more contractions and phrasal verbs.",
            "llm_instructions": "User is at B1 level; focus on expanding vocabulary and using more natural expressions in next session."
        }),
    }
    if err:
        result = mocks.get(module)
        if not result:
            return f"[ERROR in {module}: {err}]"
        return result + f" [LLM error: {err}]"
    result = mocks.get(module)
    if not result:
        return f"[WARNING: No mock found for module '{module}' - this may cause issues]"
    return result
