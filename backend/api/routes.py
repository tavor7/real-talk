"""
API routes: team_info, agent_info, model_architecture, execute.
"""
import os
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
        "description": "An AI agent that simulates realistic, slang-based conversations for language learners. It adapts to the user's proficiency and generates scenario-based dialogue practice using real-world conversational data (Reddit via RAG). The system is agent-based, supervised, and optimized to minimize LLM calls.",
        "purpose": "To give language learners authentic practice in modern slang and informal conversation (TikTok, gaming, real life) by planning scenarios, retrieving informal language patterns, generating dialogue, and reflecting on quality and level.",
        "prompt_template": {
            "template": "User profile: {user_profile}. Scenario: {scenario}. User message: {user_message}. (Optional) Learning objective: {learning_objective}."
        },
        "prompt_examples": [
            {
                "prompt": "I want to practice ordering food at a casual diner with slang.",
                "full_response": "SupervisorAgent invokes ProgramPlanner to set learning objective (ordering food, casual register). ScenarioArchitect builds a diner scenario using RAG Reddit chunks. UserEvaluation conducts the dialogue and adapts difficulty. SystemCritic reviews and approves. Final response: Here's a short dialogue to start: [Agent line]. Your turn!",
                "steps": ["SupervisorAgent", "ProgramPlanner", "ScenarioArchitect", "UserEvaluation", "SystemCritic"],
            },
            {
                "prompt": "Practice arguing about a game with a friend (B1 level).",
                "full_response": "ProgramPlanner sets objective (disagreeing politely, gaming slang). ScenarioArchitect retrieves Reddit gaming threads and builds scenario. UserEvaluation runs conversation. SystemCritic checks slang authenticity and level. Response: Scenario ready. Friend: 'That was so clutch!' You can reply with your take.",
                "steps": ["SupervisorAgent", "ProgramPlanner", "ScenarioArchitect", "UserEvaluation", "SystemCritic"],
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
    try:
        from db.supabase import get_user_profiles
        profiles = get_user_profiles()
        profile = next((p for p in profiles if str(p.get("id")) == str(req.user_profile_id)), profiles[0] if profiles else {})
        supervisor = SupervisorAgent()
        context = {
            "user_profile_id": req.user_profile_id,
            "user_profile": profile,
            "scenario": req.scenario,
            "conversation_history": req.conversation_history or [],
            "steps": [],
        }
        final_response, steps = supervisor.run(req.prompt, context)
        # Normalize steps to { module, prompt, response } per spec
        steps_out = []
        for s in steps:
            steps_out.append({
                "module": s.get("module", ""),
                "prompt": s.get("prompt", {}),
                "response": s.get("response", ""),
            })
        return {
            "status": "ok",
            "error": None,
            "response": final_response or "Agent run completed. (Mock response.)",
            "steps": steps_out,
        }
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
