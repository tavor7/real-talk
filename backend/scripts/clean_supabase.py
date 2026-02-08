#!/usr/bin/env python3
"""
Reset all Supabase data used by RealTalk.

Run from backend directory:
  python scripts/clean_supabase.py [--include-profiles]

Or from project root:
  python backend/scripts/clean_supabase.py [--include-profiles]

By default: deletes all rows from conversation_summaries and proficiency.
Use --include-profiles to also delete all user_profiles (full reset; app will use built-in profiles).
"""
import argparse
import os
import sys

# Ensure backend is on path and load .env
_backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend not in sys.path:
    sys.path.insert(0, _backend)
_root = os.path.dirname(_backend)
_env_file = os.path.join(_backend, ".env")
if os.path.isfile(_env_file):
    from dotenv import load_dotenv
    load_dotenv(_env_file)
load_dotenv(os.path.join(_root, ".env"))

from db.supabase import get_client


def main():
    parser = argparse.ArgumentParser(description="Reset Supabase tables for RealTalk.")
    parser.add_argument(
        "--include-profiles",
        action="store_true",
        help="Also delete all user_profiles (full reset; app falls back to built-in 10 profiles).",
    )
    args = parser.parse_args()

    client = get_client()
    if not client:
        print("Supabase not configured (missing SUPABASE_URL or SUPABASE_SERVICE_KEY). Nothing done.")
        return 1

    done = []

    # 1. conversation_summaries
    try:
        sel = client.table("conversation_summaries").select("id").execute()
        if sel.data:
            for row in sel.data:
                client.table("conversation_summaries").delete().eq("id", row["id"]).execute()
            done.append(f"conversation_summaries: deleted {len(sel.data)} row(s)")
        else:
            done.append("conversation_summaries: already empty")
    except Exception as e:
        done.append(f"conversation_summaries: skipped ({e})")

    # 2. proficiency
    try:
        sel = client.table("proficiency").select("user_id").execute()
        if sel.data:
            for row in sel.data:
                client.table("proficiency").delete().eq("user_id", row["user_id"]).execute()
            done.append(f"proficiency: deleted {len(sel.data)} row(s)")
        else:
            done.append("proficiency: already empty")
    except Exception as e:
        done.append(f"proficiency: skipped ({e})")

    # 3. user_profiles (optional)
    if args.include_profiles:
        try:
            sel = client.table("user_profiles").select("id").execute()
            if sel.data:
                for row in sel.data:
                    client.table("user_profiles").delete().eq("id", row["id"]).execute()
                done.append(f"user_profiles: deleted {len(sel.data)} row(s)")
            else:
                done.append("user_profiles: already empty")
        except Exception as e:
            done.append(f"user_profiles: skipped ({e})")

    for msg in done:
        print(msg)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
