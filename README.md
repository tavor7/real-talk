# SlangSpeak – Language School AI Agent

Autonomous AI agent for language schools: simulates realistic slang-based conversations, adapts to proficiency, and uses RAG over Reddit for informal language patterns.

## Architecture (strict module names)

- **SupervisorAgent** – Orchestrates flow, decides sub-agent, aggregates response
- **ProgramPlanner** – Plan & Execute: learning objective, conversation structure
- **SystemCritic** – Reflection: reviews dialogue, slang/safety/level, decides when to finish
- **ScenarioArchitect** – Builds scenarios from RAG + user profile; predefined scenarios for fast start
- **UserEvaluation** – ReAct: interacts during conversation, adapts difficulty, updates proficiency, produces summary

**Databases:** Supabase (User Information, Proficiency Level), Pinecone (Reddit embeddings for RAG).

## Environment variables (backend/.env)

| Variable | Purpose |
|----------|--------|
| `OPENAI_API_KEY` | API key for chat & embeddings |
| `OPENAI_BASE_URL` | Optional. Custom API base (e.g. `https://api.llmod.ai/v1` for LLMod.ai or Azure). Omit for api.openai.com. |
| `OPENAI_MODEL` | Chat model (default: `gpt-4o-mini`) |
| `SUPABASE_URL` | Supabase project URL (Dashboard → Settings → API) |
| `SUPABASE_SERVICE_KEY` | **Service role** key (Dashboard → Settings → API → `service_role` secret). Server-only; bypasses Row Level Security. Prefer this for backend. |
| `SUPABASE_ANON_KEY` | Alternative to service key; respects RLS (use if you don’t have service role). |
| `SUPABASE_PASSWORD` | Database password you set when creating the project. Used for direct Postgres connections; the app uses **API keys** (above), not this password, for Supabase client. You can keep it in .env for reference or other tools. |
| `PINECONE_*` | Pinecone API key, index name for RAG |
| `EMBEDDING_DIMENSION` | Must match Pinecone index: **512** or 1536. Set to 512 if your index is 512-dim so RAG retrieval works. |

**What is SUPABASE_SERVICE_KEY?**  
In Supabase: **Project Settings → API** you see two keys: **anon (public)** and **service_role (secret)**. The **service_role** key is the one to put in `SUPABASE_SERVICE_KEY`. It gives your backend full access and bypasses Row Level Security, so use it only on the server and never in the browser.

## Run locally

```bash
cd backend
pip install -r requirements.txt
# Set variables in .env (see above)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- Docs: http://localhost:8000/docs  
- Frontend: http://localhost:8000/app/

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/team_info | Static team information |
| GET | /api/agent_info | Description, purpose, prompt template, examples |
| GET | /api/model_architecture | PNG architecture diagram |
| POST | /api/execute | Main entry: `{"prompt": "...", "user_profile_id": "...", "scenario": "...", "conversation_history": []}` |
| GET | /api/user_profiles | List of user profiles (10 predefined) |

## Frontend

1. Select a user profile.
2. Choose a predefined scenario or type your own.
3. Click **Run Agent** to start; reply in the chat.
4. View final response, steps trace (module → prompt → response), and conversation summary.

## RAG (Reddit data in Pinecone)

To populate the RAG used by ScenarioArchitect:

1. **Pinecone index** – Create an index in [Pinecone Console](https://app.pinecone.io) with **dimension 1536** (for `text-embedding-3-small`). Set `PINECONE_INDEX` and optionally `PINECONE_HOST` in `.env`.

2. **Data file** – CSV or JSON with rows that have **id** and **text** (informal/slang text). See **`backend/rag/README.md`** for format and a sample file.

3. **Run the build script** (from `backend/`):
   ```bash
   cd backend
   python -m rag.build_rag rag/data/sample_reddit.json
   ```
   Use `--dry-run` to test without calling APIs; use your own CSV/JSON path for real data.

## Deployment (Render)

- Deploy backend as a web service; set env vars for OpenAI, Supabase, Pinecone.
- Keep backend public and deployment alive until graded.
