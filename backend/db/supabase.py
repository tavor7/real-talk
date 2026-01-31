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
        if url and key:
            try:
                from supabase import create_client
                _client = create_client(url, key)
            except Exception:
                _client = False  # mark as attempted so we don't retry every time
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
    """Cache proficiency update."""
    client = get_client()
    if client:
        try:
            client.table("proficiency").upsert({"user_id": user_id, **data}).execute()
        except Exception:
            pass
