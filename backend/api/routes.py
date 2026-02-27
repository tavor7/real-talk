"""
API routes: team_info, agent_info, model_architecture, execute.
"""
import os
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agents.supervisor import SupervisorAgent

router = APIRouter()

# --- Response models ---
class ExecuteRequest(BaseModel):
    prompt: str
    user_profile_id: str | None = None
    scenario: str | None = None
    conversation_history: list[dict] | None = None
    end_conversation: bool = False
    generated_scenario: dict | None = None  # Scenario from first turn, reused on subsequent turns
    session_id: str | None = None  # Server-side conversation history via Supabase (auto-generated if omitted)


# --- GET /api/team_info ---
@router.get("/team_info")
def team_info():
    return {
        "group_batch_order_number": "2_5",
        "team_name": "שגיא איתי ועמית",
        "students": [
            {"name": "Amit Tavor", "email": "amit.tavor@campus.technion.ac.il"},
            {"name": "Sagie Dekel", "email": "sagie.dekel@campus.technion.ac.il"},
            {"name": "Itay Nulman", "email": "itai.nulman@campus.technion.ac.il"},
        ],
    }


# --- GET /api/agent_info ---
@router.get("/agent_info")
def agent_info():
    return {
        "description": "An AI agent that simulates realistic, slang-based conversations for language learners. It adapts to the user's proficiency and generates scenario-based dialogue practice using real-world conversational data (Reddit via RAG). The system is agent-based, modular, and optimized to minimize LLM calls.",
        "purpose": "To give language learners authentic practice in modern slang and informal conversation (TikTok, gaming, real life) by planning scenarios, retrieving informal language patterns, generating natural dialogue, and evaluating progress.",
        "prompt_template": {
            "template": "User profile: {user_profile}. Scenario: {scenario}. User message: {user_message}. Conversation history: {conversation_hostory}(Optional) Learning objective: {learning_objective}."
        },
        "agent_pipeline": [
            "ProgramPlanner: Creates learning objectives and conversation structure based on user request and scenario",
            "RAGQueryRephraser: Converts scenario into an optimized search query for Reddit",
            "ScenarioArchitect: Designs scenario description and dialogue seeds using RAG examples",
            "ConversationPartner: Generates natural conversational responses matching scenario and user level",
            "CriticGate (from 2nd turn): Decides whether to call Critic (e.g. user said goodbye or conversation diverged from scenario)",
            "SystemCritic: When invoked, decides to end the conversation or to continue with feedback for ConversationPartner",
            "UserEvaluation: Evaluates user performance at end of conversation and generates improvement summary"
        ],
        "prompt_examples": [
            {
                "prompt": "I want to practice ordering food at a casual diner with slang.",
                "full_response": "[Scenario: You're at a greasy-spoon diner, sliding into a booth. The vibe is lowkey chill — think worn-out menus and a server who's seen it all. Time to order something comfort-food-y and shoot the breeze.]\n\nYo, what's good? You grabbing something greasy or you going light today?\n\nYour turn!",
                "steps": [
                    {
                        "module": "ProgramPlanner",
                        "prompt": {
                            "system": "You are an expert language learning planner specializing in causal and daily conversation practice.",
                            "user": "Learner Profile: Name: Alex, Interests: gaming, streaming. Scenario: ordering food at a casual diner. Plan a structured conversation."
                        },
                        "response": "{\"learning_objective\": \"Practice ordering food casually using informal expressions and slang at an A2 level.\", \"conversation_structure\": [\"greeting\", \"browse menu\", \"place order\", \"small talk\", \"pay and leave\"], \"key_vocabulary\": [\"grab a bite\", \"what's good\", \"I'll have\", \"hook me up\", \"on the side\"], \"difficulty_adjustments\": \"Keep sentences short; avoid complex idioms.\"}"
                    },
                    {
                        "module": "RAGQueryRephraser",
                        "prompt": {
                            "system": "You are an expert at crafting search queries for retrieving authentic real-life conversations.",
                            "user": "Query subject: ordering food at a casual diner. Think step by step. At the end, extract: ANSWER: {the search query}"
                        },
                        "response": "casual diner ordering food slang informal"
                    },
                    {
                        "module": "ScenarioArchitect",
                        "prompt": {
                            "system": "You are an expert scenario designer for authentic language practice.",
                            "user": "Learning Objective: Practice ordering food casually. Retrieved examples: ['yeah just gimme the usual', 'hook me up with fries on the side', 'what's the special today?']. Design a SPECIFIC scenario."
                        },
                        "response": "{\"scenario\": \"You're at a greasy-spoon diner, sliding into a booth. The vibe is lowkey chill — think worn-out menus and a server who's seen it all. Time to order something comfort-food-y and shoot the breeze.\", \"rag_examples\": [\"yeah just gimme the usual\", \"hook me up with fries on the side\"]}"
                    },
                    {
                        "module": "ConversationPartner",
                        "prompt": {
                            "system": "You are a conversation partner in a casual scenario. Reply in 1-2 short sentences, informal slang.",
                            "user": "Level: Use simple words and short sentences. Scenario: You're at a greasy-spoon diner... Start a natural conversation."
                        },
                        "response": "{\"reply\": \"Yo, what's good? You grabbing something greasy or you going light today?\"}"
                    }
                ],
            },
            {
                "prompt": "Practice arguing about a game with a friend (B1 level).",
                "full_response": "[Scenario: You and your buddy are deep in a post-match argument on Discord — your squad just got wrecked and fingers are being pointed. The vibe is friendly trash-talk mixed with actual game analysis.]\n\nBro that last round was actually painful to watch — you really pushed mid with no support lmao. What were you thinking?\n\nYour turn!",
                "steps": [
                    {
                        "module": "ProgramPlanner",
                        "prompt": {
                            "system": "You are an expert language learning planner specializing in slang and informal conversation practice.",
                            "user": "Learner Profile: Name: Maria, Level: B1, Interests: travel, TikTok. Scenario: arguing about a game with a friend. Plan a structured conversation."
                        },
                        "response": "{\"learning_objective\": \"Practice friendly disagreement and gaming slang in a natural back-and-forth at B1 level.\", \"conversation_structure\": [\"open with complaint\", \"defend position\", \"counter-argument\", \"agree to disagree\", \"plan next game\"], \"key_vocabulary\": [\"clutch\", \"toxic\", \"throw\", \"no cap\", \"we got wrecked\"], \"difficulty_adjustments\": \"Use everyday informal language and common gaming slang.\"}"
                    },
                    {
                        "module": "RAGQueryRephraser",
                        "prompt": {
                            "system": "You are an expert at crafting search queries for retrieving authentic real-life conversations.",
                            "user": "Query subject: arguing about a game with a friend. Think step by step. At the end, extract: ANSWER: {the search query}"
                        },
                        "response": "gaming slang friendly argument post-match Discord"
                    },
                    {
                        "module": "ScenarioArchitect",
                        "prompt": {
                            "system": "You are an expert scenario designer for authentic language practice.",
                            "user": "Learning Objective: Practice friendly disagreement and gaming slang. Retrieved examples: ['bro you literally inted', 'no cap that play was trash', 'clutch or kick lmao']. Design a SPECIFIC scenario."
                        },
                        "response": "{\"scenario\": \"You and your buddy are deep in a post-match argument on Discord — your squad just got wrecked and fingers are being pointed. The vibe is friendly trash-talk mixed with actual game analysis.\", \"rag_examples\": [\"bro you literally inted\", \"no cap that play was trash\", \"clutch or kick lmao\"]}"
                    },
                    {
                        "module": "ConversationPartner",
                        "prompt": {
                            "system": "You are a conversation partner in a casual scenario. Reply in 1-2 short sentences, informal slang.",
                            "user": "Level: Use everyday informal language and common slang. Scenario: You and your buddy are deep in a post-match argument on Discord... Start a natural conversation."
                        },
                        "response": "{\"reply\": \"Bro that last round was actually painful to watch — you really pushed mid with no support lmao. What were you thinking?\"}"
                    }
                ],
            },
        ],
    }


# --- GET /api/model_architecture ---
@router.get("/model_architecture")
def model_architecture():
    # Serve PNG from project/assets/architecture.png
    base = Path(__file__).resolve().parent.parent.parent
    path = base / "assets" / "architecture.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="architecture.png not found")
    return FileResponse(path, media_type="image/png")


# --- POST /api/execute (main entry) ---
@router.post("/execute")
def execute(req: ExecuteRequest, request: Request):
    print(f"\n[BACKEND] /api/execute called - end_conversation: {req.end_conversation}")
    try:
        from db.supabase import get_user_profiles
        from agents.user_evaluation import generate_end_conversation

        profiles = get_user_profiles()
        profile = next(
            (p for p in profiles if str(p.get("id")) == str(req.user_profile_id)),
            profiles[0] if profiles else {},
        )

        # --- Server-side session management ---
        # When the caller sends just {"prompt": "..."} (no session_id, no conversation_history),
        # the server uses a deterministic session key based on the caller's IP so each
        # API client gets its own isolated conversation automatically.
        session_id = req.session_id
        use_server_session = bool(session_id) or (req.conversation_history is None)
        if not session_id and req.conversation_history is None:
            client_ip = request.client.host if request.client else "unknown"
            profile_id = req.user_profile_id or str(profile.get("id", "1"))
            session_id = f"api_{client_ip}_{profile_id}"
            print(f"[SESSION] Using auto session: {session_id}")

        server_session = None
        if use_server_session and session_id:
            try:
                from db.supabase import get_cli_session
                server_session = get_cli_session(session_id)
                if server_session:
                    print(f"[SESSION] Loaded session {session_id[:8]}...: {len(server_session.get('conversation_history') or [])} messages")
            except Exception as e:
                print(f"[SESSION] Error loading session: {e}")

        effective_history = req.conversation_history
        effective_generated_scenario = req.generated_scenario
        effective_scenario = req.scenario
        if server_session:
            effective_history = server_session.get("conversation_history") or []
            effective_generated_scenario = server_session.get("generated_scenario")
            effective_scenario = server_session.get("scenario") or req.scenario

        if req.end_conversation:
            print("\n" + "="*80)
            print("[BACKEND] End conversation request received")
            print(f"[BACKEND] User profile ID: {req.user_profile_id}")
            print(f"[BACKEND] Scenario: {effective_scenario}")
            print(f"[BACKEND] Conversation history length: {len(effective_history or [])}")
            print("="*80)
            
            reply, summary, llm_instructions = generate_end_conversation(
                profile,
                effective_history or [],
                effective_scenario or "Casual conversation",
            )
            
            print(f"[BACKEND] Generated reply: {reply[:100]}...")
            print(f"[BACKEND] Summary length: {len(summary)} chars")
            print(f"[BACKEND] LLM instructions length: {len(llm_instructions)} chars")
            print("="*80 + "\n")
            user_id = (req.user_profile_id or profile.get("id") or "").strip()
            if user_id:
                try:
                    from db.supabase import upsert_proficiency, save_conversation_summary
                    print(f"[BACKEND] Saving to Supabase for user_id: {user_id}")
                    upsert_proficiency(user_id, {
                        "last_scenario": effective_scenario or "Casual conversation",
                        "last_summary": summary[:2000] if summary else "",
                    })
                    print(f"[BACKEND] ✓ Proficiency saved to Supabase")
                    save_conversation_summary(
                        user_id,
                        effective_scenario or "Casual conversation",
                        summary,
                        llm_instructions,
                    )
                    print(f"[BACKEND] ✓ Conversation summary saved to Supabase")
                except Exception as e:
                    print(f"[BACKEND] ✗ Error saving to Supabase: {e}")
                    import traceback
                    traceback.print_exc()
            if use_server_session and session_id:
                try:
                    from db.supabase import delete_cli_session
                    delete_cli_session(session_id)
                    print(f"[SESSION] Session deleted: {session_id[:8]}...")
                except Exception as e:
                    print(f"[SESSION] Error deleting session: {e}")
            result = {
                "status": "ok",
                "error": None,
                "response": summary,
                "steps": [{"module": "UserEvaluation", "prompt": {"end_conversation": True}, "response": summary or "(end conversation)"}],
            }
            if req.conversation_history is not None:
                result["reply"] = summary
                result["conversation_ended"] = True
            return result

        # Load previous conversation summaries + LLM instructions for this profile (from Supabase)
        profile_ctx = ""
        generated_scenario_from_db = None
        if req.user_profile_id:
            try:
                from db.supabase import get_profile_conversation_context, get_proficiency
                profile_ctx = get_profile_conversation_context(req.user_profile_id)

                # Load last_scenario from Supabase if neither request nor CLI session provided it
                if not effective_generated_scenario:
                    proficiency = get_proficiency(req.user_profile_id)
                    if proficiency and proficiency.get("last_scenario"):
                        try:
                            generated_scenario_from_db = json.loads(proficiency.get("last_scenario"))
                            print(f"[SAVE] Loaded scenario from Supabase: {generated_scenario_from_db.get('scenario', 'N/A')}")
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                print(f"[SAVE] Error loading from Supabase: {e}")
        supervisor = SupervisorAgent()
        # Use generated_scenario from CLI session / request, or fall back to one loaded from DB
        scenario_to_use = effective_generated_scenario or generated_scenario_from_db
        context = {
            "user_profile_id": req.user_profile_id,
            "user_profile": profile,
            "scenario": effective_scenario,
            "conversation_history": effective_history or [],
            "profile_conversation_context": profile_ctx,
            "generated_scenario": scenario_to_use,
            "steps": [],
        }
        final_response, steps, reply, generated_scenario, conversation_ended_by_critic = supervisor.run(req.prompt, context)

        # When Critic decided to end: run UserEvaluation and save like "end conversation by user"
        if conversation_ended_by_critic:
            print("\n[BACKEND] Conversation ended by Critic — running UserEvaluation")
            history_for_eval = list(effective_history or [])
            if req.prompt:
                history_for_eval.append({"role": "user", "content": req.prompt})
            eval_reply, summary, llm_instructions = generate_end_conversation(
                profile,
                history_for_eval,
                effective_scenario or (generated_scenario.get("scenario") if generated_scenario else "Casual conversation"),
            )
            user_id = (req.user_profile_id or profile.get("id") or "").strip()
            if user_id:
                try:
                    from db.supabase import upsert_proficiency, save_conversation_summary
                    upsert_proficiency(user_id, {
                        "last_scenario": effective_scenario or "Casual conversation",
                        "last_summary": summary[:2000] if summary else "",
                    })
                    save_conversation_summary(user_id, effective_scenario or "Casual conversation", summary, llm_instructions)
                    print("[BACKEND] ✓ Proficiency and summary saved (Critic end)")
                except Exception as e:
                    print(f"[BACKEND] ✗ Error saving after Critic end: {e}")
            if use_server_session and session_id:
                try:
                    from db.supabase import delete_cli_session
                    delete_cli_session(session_id)
                    print(f"[SESSION] Session deleted (Critic end): {session_id[:8]}...")
                except Exception as e:
                    print(f"[SESSION] Error deleting session: {e}")
            steps_out = []
            for s in steps:
                resp = s.get("response")
                if resp is None or (isinstance(resp, str) and not resp.strip()):
                    resp = "(empty or null — no response from this step)"
                steps_out.append({
                    "module": s.get("module", ""),
                    "prompt": s.get("prompt", {}),
                    "response": resp if isinstance(resp, str) else str(resp),
                })
            result = {
                "status": "ok",
                "error": None,
                "response": summary,
                "steps": steps_out,
            }
            if req.conversation_history is not None:
                result["reply"] = reply or None
                result["conversation_ended"] = True
            return result

        # Store generated scenario to Supabase for persistence across sessions
        user_id = (req.user_profile_id or profile.get("id") or "").strip()
        if user_id and generated_scenario:
            try:
                from db.supabase import upsert_proficiency
                print(f"[SAVE] Saving scenario to Supabase: {generated_scenario.get('scenario', 'N/A')}")
                upsert_proficiency(user_id, {
                    "last_scenario": json.dumps(generated_scenario),
                })
                print(f"[SAVE] Saved successfully")
            except Exception as e:
                print(f"[SAVE] Error saving: {e}")

        if use_server_session and session_id:
            try:
                from db.supabase import save_cli_session
                updated_history = list(effective_history or [])
                if req.prompt:
                    updated_history.append({"role": "user", "content": req.prompt})
                if reply:
                    updated_history.append({"role": "assistant", "content": reply})
                save_cli_session(
                    session_id,
                    req.user_profile_id or str(profile.get("id", "")),
                    effective_scenario or req.prompt,
                    updated_history,
                    generated_scenario,
                )
                print(f"[SESSION] Session saved: {len(updated_history)} messages")
            except Exception as e:
                print(f"[SESSION] Error saving session: {e}")

        # Normalize steps to { module, prompt, response } per spec
        steps_out = []
        for s in steps:
            resp = s.get("response")
            if resp is None or (isinstance(resp, str) and not resp.strip()):
                resp = "(empty or null — no response from this step)"
            steps_out.append({
                "module": s.get("module", ""),
                "prompt": s.get("prompt", {}),
                "response": resp if isinstance(resp, str) else str(resp),
            })
        result = {
            "status": "ok",
            "error": None,
            "response": reply or final_response or "No response generated.",
            "steps": steps_out,
        }
        if req.conversation_history is not None:
            result["reply"] = reply or None
            result["generated_scenario"] = generated_scenario
            result["conversation_ended"] = False
        return result
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "response": None,
            "steps": [],
        }


# --- User profiles (for frontend) ---
@router.get("/user_profiles")
def user_profiles():
    from db.supabase import get_user_profiles
    return get_user_profiles()
