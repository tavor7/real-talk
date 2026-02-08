"""
Supabase: User Information DB + Proficiency Level DB.
"""
import os
from typing import Any

# Lazy init to avoid import errors if supabase not configured
_client = None


def get_client():
    global _client
    if _client is None:
        url = (os.environ.get("SUPABASE_URL") or "").strip()
        key = (os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or "").strip()
        print(f"[Supabase] Checking configuration - URL: {'set' if url else 'NOT SET'}, Key: {'set' if key else 'NOT SET'}")
        if url and key:
            try:
                from supabase import create_client
                print(f"[Supabase] Creating client with URL: {url[:50]}...")
                _client = create_client(url, key)
                print(f"[Supabase] ✓ Client created successfully")
            except ImportError as e:
                print(f"[Supabase] ✗ Import error: supabase package not installed. Run: pip install supabase")
                _client = False
            except Exception as e:
                print(f"[Supabase] ✗ Error creating client: {e}")
                import traceback
                traceback.print_exc()
                _client = False  # mark as attempted so we don't retry every time
        else:
            print(f"[Supabase] ✗ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY/SUPABASE_ANON_KEY")
            _client = False
    return _client if _client is not False else None


def get_user_profiles() -> list[dict[str, Any]]:
    """Return list of user profiles (from DB or fallback to 10 pre-generated)."""
    client = get_client()
    if client:
        try:
            r = client.table("user_profiles").select("*").execute()
            if r.data:
                return r.data
        except Exception:
            pass
    return _default_profiles()


def _default_profiles() -> list[dict[str, Any]]:
    """10 realistic user profiles for language school."""
    return [
        {"id": "1", "name": "Alex", "level": "A2", "goals": "gaming, streaming", "age_group": "18-25"},
        {"id": "2", "name": "Maria", "level": "B1", "goals": "travel, TikTok", "age_group": "25-35"},
        {"id": "3", "name": "Jordan", "level": "B2", "goals": "work meetings, slang", "age_group": "30-40"},
        {"id": "4", "name": "Sam", "level": "A1", "goals": "basics, memes", "age_group": "16-22"},
        {"id": "5", "name": "Casey", "level": "C1", "goals": "native-like informal", "age_group": "28-35"},
        {"id": "6", "name": "Riley", "level": "A2", "goals": "dating app, friends", "age_group": "20-28"},
        {"id": "7", "name": "Taylor", "level": "B1", "goals": "podcasts, Reddit", "age_group": "22-30"},
        {"id": "8", "name": "Morgan", "level": "B2", "goals": "gaming voice chat", "age_group": "18-26"},
        {"id": "9", "name": "Quinn", "level": "A2", "goals": "travel, casual chat", "age_group": "25-35"},
        {"id": "10", "name": "Jamie", "level": "B1", "goals": "social media, slang", "age_group": "19-27"},
    ]


def get_proficiency(user_id: str) -> dict[str, Any] | None:
    """Get cached proficiency for user."""
    client = get_client()
    if client:
        try:
            r = client.table("proficiency").select("*").eq("user_id", user_id).limit(1).execute()
            if r.data:
                return r.data[0]
        except Exception:
            pass
    return None


def upsert_proficiency(user_id: str, data: dict[str, Any]) -> None:
    """Cache proficiency update (last_scenario, last_summary)."""
    client = get_client()
    if client:
        try:
            result = client.table("proficiency").upsert({"user_id": user_id, **data}).execute()
            print(f"[Supabase] Proficiency upserted for user_id: {user_id}")
        except Exception as e:
            print(f"[Supabase] Error upserting proficiency: {e}")
            raise
    else:
        print(f"[Supabase] No client available (SUPABASE_URL or SUPABASE_SERVICE_KEY not set)")


# --- Conversation summaries (saved when user ends conversation) ---

def save_conversation_summary(
    user_profile_id: str,
    scenario_name: str,
    summary: str,
    llm_instructions: str = "",
) -> None:
    """Append a conversation summary and LLM instructions for this profile."""
    client = get_client()
    if not client:
        print(f"[Supabase] No client available (SUPABASE_URL or SUPABASE_SERVICE_KEY not set)")
        return
    if not user_profile_id.strip():
        print(f"[Supabase] Empty user_profile_id, skipping save")
        return
    try:
        result = client.table("conversation_summaries").insert({
            "user_profile_id": user_profile_id.strip(),
            "scenario_name": (scenario_name or "")[:500],
            "summary": (summary or "")[:8000],
            "llm_instructions": (llm_instructions or "")[:2000],
        }).execute()
        print(f"[Supabase] Conversation summary saved for user_profile_id: {user_profile_id.strip()}")
    except Exception as e:
        print(f"[Supabase] Error saving conversation summary: {e}")
        raise


def get_profile_conversation_context(user_profile_id: str, max_summaries: int = 5) -> str:
    """Return a single string of previous summaries + latest LLM instructions for use in the next conversation.
    Empty string if no data. Used to inject into LLM context when starting a new conversation.
    """
    client = get_client()
    if not client:
        print(f"[Supabase] No client available, cannot load conversation context")
        return ""
    if not user_profile_id.strip():
        print(f"[Supabase] Empty user_profile_id, cannot load conversation context")
        return ""
    try:
        print(f"[Supabase] Querying conversation_summaries for user_profile_id: {user_profile_id.strip()}")
        r = (
            client.table("conversation_summaries")
            .select("summary, llm_instructions, scenario_name, created_at")
            .eq("user_profile_id", user_profile_id.strip())
            .order("created_at", desc=True)
            .limit(max_summaries)
            .execute()
        )
        if not r.data:
            print(f"[Supabase] No conversation summaries found for user_profile_id: {user_profile_id.strip()}")
            return ""
        print(f"[Supabase] Found {len(r.data)} conversation summary(ies)")
        parts = []
        instructions = []
        for row in r.data:
            if row.get("llm_instructions"):
                instructions.append(row["llm_instructions"])
            s = row.get("summary", "").strip()
            scenario = (row.get("scenario_name") or "").strip()
            if s:
                parts.append(f"- [{scenario or 'Session'}]: {s[:600]}")
        out = ""
        if parts:
            out = "Previous session summaries (use for continuity):\n" + "\n".join(parts)
        if instructions:
            out += "\n\nInstructions for this conversation (follow these): " + instructions[0]
        result = out.strip()
        print(f"[Supabase] ✓ Conversation context built ({len(result)} chars)")
        return result
    except Exception as e:
        print(f"[Supabase] Error loading conversation context: {e}")
        import traceback
        traceback.print_exc()
        return ""
