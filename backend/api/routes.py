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
    end_conversation: bool = False


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
        from agents.user_evaluation import generate_end_conversation

        profiles = get_user_profiles()
        profile = next(
            (p for p in profiles if str(p.get("id")) == str(req.user_profile_id)),
            profiles[0] if profiles else {},
        )

        if req.end_conversation:
            reply, summary, llm_instructions = generate_end_conversation(
                profile,
                req.conversation_history or [],
                req.scenario or "Casual conversation",
            )
            user_id = (req.user_profile_id or profile.get("id") or "").strip()
            if user_id:
                try:
                    from db.supabase import upsert_proficiency, save_conversation_summary
                    upsert_proficiency(user_id, {
                        "last_scenario": req.scenario or "Casual conversation",
                        "last_summary": summary[:2000] if summary else "",
                    })
                    save_conversation_summary(
                        user_id,
                        req.scenario or "Casual conversation",
                        summary,
                        llm_instructions,
                    )
                except Exception:
                    pass
            final_response = f"{reply}\n\n[Summary] {summary}"
            return {
                "status": "ok",
                "error": None,
                "response": final_response,
                "reply": reply,
                "steps": [{"module": "UserEvaluation", "prompt": {"end_conversation": True}, "response": summary or "(end conversation)"}],
            }

        # Load previous conversation summaries + LLM instructions for this profile (from Supabase)
        profile_ctx = ""
        if req.user_profile_id:
            try:
                from db.supabase import get_profile_conversation_context
                profile_ctx = get_profile_conversation_context(req.user_profile_id)
            except Exception:
                pass
        supervisor = SupervisorAgent()
        context = {
            "user_profile_id": req.user_profile_id,
            "user_profile": profile,
            "scenario": req.scenario,
            "conversation_history": req.conversation_history or [],
            "profile_conversation_context": profile_ctx,
            "steps": [],
        }
        final_response, steps, reply = supervisor.run(req.prompt, context)
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
            "steps": steps_out,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "response": None,
            "reply": None,
            "steps": [],
        }


# --- User profiles (for frontend) ---
@router.get("/user_profiles")
def user_profiles():
    from db.supabase import get_user_profiles
    return get_user_profiles()
