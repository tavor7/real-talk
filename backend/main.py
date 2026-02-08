"""
Language School AI Agent - Main entry point.
Orchestrates SupervisorAgent, ProgramPlanner, SystemCritic, ScenarioArchitect, UserEvaluation.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load .env so the same key as in LiteLLM token table is used (no extra chars)
_backend_dir = Path(__file__).resolve().parent
_project_root = _backend_dir.parent
for _p in (_backend_dir / ".env", _project_root / ".env"):
    if _p.exists():
        load_dotenv(_p)
        break
else:
    load_dotenv(_backend_dir / ".env")

from api.routes import router

app = FastAPI(title="Language School AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api", tags=["api"])

# Serve architecture diagram from assets (if running from project root)
_project_root = os.path.dirname(os.path.dirname(__file__))
assets_path = os.path.join(_project_root, "assets")
if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

# Serve frontend
frontend_path = os.path.join(_project_root, "frontend")
if os.path.exists(frontend_path):
    app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")


@app.get("/")
def root():
    return {"message": "Language School AI Agent API", "docs": "/docs", "app": "/app/"}
