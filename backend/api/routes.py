"""
API routes: team_info, agent_info, model_architecture, execute.
"""
import os
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
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


# --- GET /api/team_info ---
@router.get("/team_info")
def team_info():
    return {
        "group_batch_order_number": "1_1",
        "team_name": "RealTalk Team",
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
            "template": "User profile: {user_profile}. Scenario: {scenario}. User message: {user_message}. (Optional) Learning objective: {learning_objective}."
        },
        "agent_pipeline": [
            "ProgramPlanner: Creates learning objectives and conversation structure based on user request and scenario",
            "RAGQueryRephraser: Converts scenario into an optimized search query for Reddit",
            "ScenarioArchitect: Designs scenario description and dialogue seeds using RAG examples",
            "ConversationPartner: Generates natural conversational responses matching scenario and user level",
            "UserEvaluation: Evaluates user performance at end of conversation and generates improvement summary"
        ],
        "prompt_examples": [
            {
                "prompt": "I want to practice ordering food at a casual diner with slang.",
                "response": "ProgramPlanner creates objective (ordering food, casual register). RAGQueryRephraser optimizes search. ScenarioArchitect builds diner scenario. ConversationPartner generates opening: 'Hey! Grabbing a bite?' User responds, ConversationPartner continues dialogue naturally. At session end, UserEvaluation provides summary: 'Focus on using more slang expressions, practice ordering variations.'",
                "steps": ["ProgramPlanner", "RAGQueryRephraser", "ScenarioArchitect", "ConversationPartner", "UserEvaluation (at end)"],
            },
            {
                "prompt": "Practice arguing about a game with a friend (B1 level).",
                "response": "ProgramPlanner sets objective (gaming slang, friendly disagreement). ScenarioArchitect retrieves Reddit gaming threads, builds scenario. ConversationPartner opens conversation with B1-appropriate slang. Natural dialogue flow based on RAG examples. UserEvaluation at end: 'Good job using 'clutch' and 'toxic'—work on longer turns.'",
                "steps": ["ProgramPlanner", "RAGQueryRephraser", "ScenarioArchitect", "ConversationPartner"],
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
def execute(req: ExecuteRequest):
    print(f"\n[BACKEND] /api/execute called - end_conversation: {req.end_conversation}")
    try:
        from db.supabase import get_user_profiles
        from agents.user_evaluation import generate_end_conversation

        profiles = get_user_profiles()
        profile = next(
            (p for p in profiles if str(p.get("id")) == str(req.user_profile_id)),
            profiles[0] if profiles else {},
        )

        if req.end_conversation:
            print("\n" + "="*80)
            print("[BACKEND] End conversation request received")
            print(f"[BACKEND] User profile ID: {req.user_profile_id}")
            print(f"[BACKEND] Scenario: {req.scenario}")
            print(f"[BACKEND] Conversation history length: {len(req.conversation_history or [])}")
            print("="*80)
            
            reply, summary, llm_instructions = generate_end_conversation(
                profile,
                req.conversation_history or [],
                req.scenario or "Casual conversation",
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
                        "last_scenario": req.scenario or "Casual conversation",
                        "last_summary": summary[:2000] if summary else "",
                    })
                    print(f"[BACKEND] ✓ Proficiency saved to Supabase")
                    save_conversation_summary(
                        user_id,
                        req.scenario or "Casual conversation",
                        summary,
                        llm_instructions,
                    )
                    print(f"[BACKEND] ✓ Conversation summary saved to Supabase")
                except Exception as e:
                    print(f"[BACKEND] ✗ Error saving to Supabase: {e}")
                    import traceback
                    traceback.print_exc()
            return {
                "status": "ok",
                "error": None,
                "response": summary,
                "reply": summary,
                "steps": [{"module": "UserEvaluation", "prompt": {"end_conversation": True}, "response": summary or "(end conversation)"}],
            }

        # Load previous conversation summaries + LLM instructions for this profile (from Supabase)
        profile_ctx = ""
        generated_scenario_from_db = None
        if req.user_profile_id:
            try:
                from db.supabase import get_profile_conversation_context, get_proficiency
                profile_ctx = get_profile_conversation_context(req.user_profile_id)
                
                # Load last_scenario from Supabase if frontend didn't provide it
                if not req.generated_scenario:
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
        # Use generated_scenario from request, or fall back to one loaded from DB
        scenario_to_use = req.generated_scenario or generated_scenario_from_db
        context = {
            "user_profile_id": req.user_profile_id,
            "user_profile": profile,
            "scenario": req.scenario,
            "conversation_history": req.conversation_history or [],
            "profile_conversation_context": profile_ctx,
            "generated_scenario": scenario_to_use,  # Use scenario from request or DB
            "steps": [],
        }
        final_response, steps, reply, generated_scenario = supervisor.run(req.prompt, context)
        
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
        return {
            "status": "ok",
            "error": None,
            "response": final_response or "No response generated.",
            "reply": reply or None,  # plain agent message for conversation history (opening line or follow-up)
            "generated_scenario": generated_scenario,  # Include generated scenario so frontend can persist it
            "steps": steps_out,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "response": None,
            "reply": None,
            "generated_scenario": None,
            "steps": [],
        }


# --- User profiles (for frontend) ---
@router.get("/user_profiles")
def user_profiles():
    from db.supabase import get_user_profiles
    return get_user_profiles()
