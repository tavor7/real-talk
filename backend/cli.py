"""
RealTalk CLI — command-line interface for practising English with the agent.

Usage:
    python cli.py                          # default profile + default scenario
    python cli.py --profile 2             # pick profile by id
    python cli.py --scenario "gaming"     # pick scenario by keyword

Type your message and press Enter to chat.
Type  'end', 'quit', or 'exit'  to end the conversation and receive your evaluation.

Conversation history is stored server-side in Supabase for the duration of the
conversation and is deleted when the conversation ends.
"""

import argparse
import json
import sys
import uuid
import os
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

DEFAULT_SCENARIO = "Casual conversation"

# Keywords for pre-defined scenarios (from scenario_architect.py PREDEFINED_SCENARIOS)
PREDEFINED_SCENARIOS = [
    {"id": "coffee",    "name": "Casual chat at a coffee shop",      "hint": "coffee shop small talk slang"},
    {"id": "gaming",    "name": "Arguing about a game with a friend", "hint": "gaming slang argument"},
    {"id": "party",     "name": "Meeting someone at a party",         "hint": "party introduction slang"},
    {"id": "streaming", "name": "Talking like a streamer to viewers", "hint": "streaming slang viewers"},
    {"id": "diner",     "name": "Ordering food at a casual diner",    "hint": "ordering food casual slang"},
]

END_COMMANDS = {"end", "quit", "exit", "bye", "q"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pick_profile(profiles: list[dict], profile_arg: str | None) -> dict:
    if profile_arg:
        match = next(
            (p for p in profiles if str(p.get("id")) == profile_arg or
             p.get("name", "").lower() == profile_arg.lower()),
            None,
        )
        if match:
            return match
        print(f"[CLI] Profile '{profile_arg}' not found — using default.")
    return profiles[0]


def pick_scenario(scenario_arg: str | None) -> str:
    if scenario_arg:
        lower = scenario_arg.lower()
        match = next(
            (s for s in PREDEFINED_SCENARIOS if lower in s["id"] or lower in s["name"].lower()),
            None,
        )
        if match:
            return match["name"]
        # Treat as a free-form scenario description
        return scenario_arg
    return DEFAULT_SCENARIO


def print_separator(char: str = "─", width: int = 60) -> None:
    print(char * width)


def call_execute(api_base: str, payload: dict) -> dict:
    url = f"{api_base}/api/execute"
    resp = requests.post(url, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def fetch_profiles(api_base: str) -> list[dict]:
    try:
        resp = requests.get(f"{api_base}/api/user_profiles", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[CLI] Could not fetch profiles from server ({e}). Using built-in defaults.")
        return [
            {"id": "1",  "name": "Alex",   "level": "A2", "goals": "gaming, streaming"},
            {"id": "2",  "name": "Maria",  "level": "B1", "goals": "travel, TikTok"},
            {"id": "3",  "name": "Jordan", "level": "B2", "goals": "work meetings, slang"},
            {"id": "4",  "name": "Sam",    "level": "A1", "goals": "basics, memes"},
            {"id": "5",  "name": "Casey",  "level": "C1", "goals": "native-like informal"},
        ]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="RealTalk CLI — practice daily English with an AI partner."
    )
    parser.add_argument(
        "--api", default=DEFAULT_API_BASE,
        help=f"Backend URL (default: {DEFAULT_API_BASE})",
    )
    parser.add_argument(
        "--profile", default=None,
        help="Profile id or name (default: first profile — Alex, A2)",
    )
    parser.add_argument(
        "--scenario", default=None,
        help="Scenario keyword or description (default: 'Casual conversation'). "
             "Options: coffee, gaming, party, streaming, diner",
    )
    args = parser.parse_args()

    api_base = args.api.rstrip("/")

    # ------------------------------------------------------------------
    # Select profile and scenario
    # ------------------------------------------------------------------
    profiles = fetch_profiles(api_base)
    profile = pick_profile(profiles, args.profile)
    scenario = pick_scenario(args.scenario)

    session_id = str(uuid.uuid4())

    print()
    print_separator("═")
    print("  RealTalk — Command-Line English Practice")
    print_separator("═")
    print(f"  Profile : {profile.get('name')} | Level: {profile.get('level')} | Interests: {profile.get('goals', '—')}")
    print(f"  Scenario: {scenario}")
    print(f"  Session : {session_id[:8]}...")
    print_separator("─")
    print("  Type your message and press Enter to chat.")
    print(f"  Type  end / quit / exit  to finish and get your evaluation.")
    print_separator("═")
    print()

    # ------------------------------------------------------------------
    # Start conversation (first turn — no user message yet)
    # ------------------------------------------------------------------
    print("⏳  Starting scenario…", end=" ", flush=True)
    try:
        data = call_execute(api_base, {
            "prompt": scenario,
            "user_profile_id": str(profile.get("id")),
            "scenario": scenario,
            "end_conversation": False,
            "session_id": session_id,
        })
    except Exception as e:
        print(f"\n[CLI] Error contacting backend: {e}")
        sys.exit(1)

    if data.get("status") == "error":
        print(f"\n[CLI] Backend error: {data.get('error')}")
        sys.exit(1)

    opening = data.get("reply") or data.get("response") or ""
    print(f"\r🤖  {opening}")
    print()

    # ------------------------------------------------------------------
    # Conversation loop
    # ------------------------------------------------------------------
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = "exit"

        if not user_input:
            continue

        # End command
        if user_input.lower() in END_COMMANDS:
            print()
            print("⏳  Ending conversation and generating your evaluation…")
            try:
                data = call_execute(api_base, {
                    "prompt": "",
                    "user_profile_id": str(profile.get("id")),
                    "scenario": scenario,
                    "end_conversation": True,
                    "session_id": session_id,
                })
            except Exception as e:
                print(f"[CLI] Error contacting backend: {e}")
                break

            evaluation = data.get("response") or data.get("reply") or "No evaluation available."
            print()
            print_separator("═")
            print("  📊  Evaluation")
            print_separator("─")
            print(evaluation)
            print_separator("═")
            break

        # Normal turn
        print("⏳ ", end="", flush=True)
        try:
            data = call_execute(api_base, {
                "prompt": user_input,
                "user_profile_id": str(profile.get("id")),
                "scenario": scenario,
                "end_conversation": False,
                "session_id": session_id,
            })
        except Exception as e:
            print(f"\r[CLI] Error: {e}")
            continue

        if data.get("status") == "error":
            print(f"\r[CLI] Backend error: {data.get('error')}")
            continue

        reply = data.get("reply") or data.get("response") or "…"
        print(f"\r🤖  {reply}")

        # Critic ended the conversation
        if data.get("conversation_ended"):
            evaluation = data.get("response") or reply
            print()
            print_separator("═")
            print("  📊  Evaluation")
            print_separator("─")
            print(evaluation)
            print_separator("═")
            break

        print()


if __name__ == "__main__":
    main()
