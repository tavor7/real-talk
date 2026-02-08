# RealTalk – Language School AI Agent

Autonomous AI agent for language schools: simulates realistic slang-based conversations, adapts to proficiency, and uses RAG over Reddit for informal language patterns.

## Architecture (strict module names)

- **SupervisorAgent** – Orchestrates flow, decides sub-agent, aggregates response
- **ProgramPlanner** – Plan & Execute: learning objective, conversation structure
- **SystemCritic** – Reflection: reviews dialogue, slang/safety/level, decides when to finish
- **ScenarioArchitect** – Builds scenarios from RAG + user profile; predefined scenarios for fast start
- **UserEvaluation** – ReAct: interacts during conversation, adapts difficulty, updates proficiency, produces summary

**Databases:** 
- **Supabase** – User Information DB (10 profiles), Proficiency Level DB (last scenario/summary), Conversation Summaries (saved when user ends conversation; includes LLM instructions for next session)
- **Pinecone** – Vector DB for Reddit embeddings (RAG)

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
| `LLM_PROMPT_MAX_LENGTH` | Optional. If set (e.g. `2000`), prompts longer than this are truncated before sending to LLM. If not set, full prompts are sent. |
| `LLM_MAX_TOKENS` | Optional. If set (e.g. `2000`), LLM responses are capped at this token count. If not set, no limit (uses model default, typically 4096+). |

**What is SUPABASE_SERVICE_KEY?**  
In Supabase: **Project Settings → API** you see two keys: **anon (public)** and **service_role (secret)**. The **service_role** key is the one to put in `SUPABASE_SERVICE_KEY`. It gives your backend full access and bypasses Row Level Security, so use it only on the server and never in the browser.

## Run locally

```bash
cd backend
pip install -r requirements.txt
# Set variables in .env (see above)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**After starting the server:**

1. **Open the frontend** – Navigate to http://localhost:8000/app/ in your browser
2. **Test the API** – Visit http://localhost:8000/docs to see the interactive API documentation (Swagger UI)
3. **Start a conversation** – In the frontend:
   - Select a user profile (e.g., Alex, A2 level)
   - Choose or type a scenario
   - Click **Run Agent** to begin
4. **Verify setup** – If you see errors, check:
   - `.env` file has all required variables (see [Environment variables](#environment-variables-backendenv))
   - Supabase tables are created (see [Supabase Setup](#supabase-setup))
   - Pinecone index exists if using RAG (see [RAG](#rag-reddit-data-in-pinecone))

**Available URLs:**
- Frontend: http://localhost:8000/app/
- API docs: http://localhost:8000/docs
- API base: http://localhost:8000

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/team_info | Static team information |
| GET | /api/agent_info | Description, purpose, prompt template, examples |
| GET | /api/model_architecture | PNG architecture diagram |
| POST | /api/execute | Main entry: `{"prompt": "...", "user_profile_id": "...", "scenario": "...", "conversation_history": [], "end_conversation": false}`<br>Set `end_conversation: true` to end conversation and get summary. Returns `reply` (plain message) and `response` (full with summary). |
| GET | /api/user_profiles | List of user profiles (10 predefined) |

## Frontend

1. Select a user profile (e.g. Alex, A2 level, into gaming/streaming).
2. Choose a predefined scenario or type your own.
3. Click **Run Agent** to start the conversation.
4. The agent will talk **TO** you (as the chosen profile). For example, if you selected "Alex", the agent acts as a barista/friend talking TO Alex, not AS Alex.
5. Reply in the chat; the agent adapts to your level and stays on topic.
6. Click **End conversation** to get a summary and practice tips. The conversation summary and LLM instructions are saved to Supabase for use in your next session.
7. Click **Chat again** to reset and start a new conversation.
8. View **Steps trace** to see full prompts and responses from each agent (ProgramPlanner, ScenarioArchitect, UserEvaluation, SystemCritic).

## RAG (Reddit data in Pinecone)

To populate the RAG used by ScenarioArchitect:

1. **Pinecone index** – Create an index in [Pinecone Console](https://app.pinecone.io) with **dimension 512** (default) or **1536**. Set `PINECONE_INDEX` and optionally `PINECONE_HOST` in `.env`. Set `EMBEDDING_DIMENSION=512` if your index is 512-dim.

2. **Data file** – CSV or JSON with rows that have **id** and **text** (informal/slang text). See **`backend/rag/README.md`** for format and a sample file.

3. **Run the build script** (from `backend/`):
   ```bash
   cd backend
   python -m rag.build_rag rag/data/sample_reddit.json
   ```
   Use `--dry-run` to test without calling APIs; use your own CSV/JSON path for real data.

**Note:** RAG retrieval happens on every user message. The query combines scenario + user profile goals + recent conversation, so chunks are relevant to the current topic.

## Supabase Setup

1. **Create tables** – Run `backend/supabase_schema.sql` in Supabase Dashboard → SQL Editor to create:
   - `user_profiles` – 10 predefined profiles (or add your own)
   - `proficiency` – Stores last scenario and summary per user
   - `conversation_summaries` – Stores conversation summaries and LLM instructions for continuity

2. **Clean/reset data** – To reset all conversation data:
   ```bash
   cd backend
   python scripts/clean_supabase.py
   # Or to also delete user_profiles:
   python scripts/clean_supabase.py --include-profiles
   ```

## Conversation Flow

- **Scenario description**: Shows "You're practicing as [Profile Name]..." to clarify the learner is practicing AS the chosen profile.
- **Agent role**: The agent talks **TO** the learner (e.g. barista, friend), not AS the learner. The agent never says "I'm [Profile Name]" — it says "Hey [Profile Name]!" or similar.
- **RAG retrieval**: On every user message, ScenarioArchitect builds a query from: scenario hint + user profile goals + recent conversation messages (last 2-4 messages). This ensures retrieved Reddit chunks are relevant to both the scenario and the current topic.
- **Conversation continuity**: When you end a conversation, a summary and LLM instructions are saved to Supabase. When you start a new conversation with the same profile, the agent uses previous summaries (last 5) and the latest LLM instructions for context.
- **Steps trace**: Shows full prompts and responses from all agents (no truncation). Character counts are displayed in the summary for verification.
- **Button behavior**: Run Agent, Send, and End conversation buttons are disabled during requests to prevent double submissions.

## Agent Details

### SystemCritic
- **Assesses only the learner (user) messages** — not the assistant/agent responses
- The assistant's lines are provided for conversation context only
- Checks: safety, clarity, and appropriateness for the learner's CEFR level
- Decides when to finish the conversation

### UserEvaluation
- Acts as the **conversation partner** talking TO the learner
- Adapts difficulty based on the learner's CEFR level (A1-C2)
- Uses previous conversation summaries and LLM instructions when available
- Generates summary and LLM instructions when conversation ends
- Follows conversation flow: stays on topic, acknowledges user preferences, answers "and you?" in the same context

## Debugging

### Debug LLM responses
If you're getting empty responses from the LLM, run with debug logging:
```bash
cd backend
DEBUG_LLM=1 python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
This prints raw API responses to stderr when content is empty, helping diagnose provider-specific issues.

### Empty responses from ScenarioArchitect/SystemCritic
- These agents run 2nd and 4th in the flow, so they may hit rate limits
- The code includes delays (1.2s for ScenarioArchitect, 1.0s for SystemCritic) and retries
- If still empty, check your provider's rate limits or try a different model

### Steps trace shows "(empty or null)"
- This means the LLM returned empty content
- Check browser console for errors
- Verify `OPENAI_API_KEY` and `OPENAI_MODEL` are correct
- Run with `DEBUG_LLM=1` to see raw API responses

## Deployment (Render)

- Deploy backend as a web service; set env vars for OpenAI, Supabase, Pinecone.
- Keep backend public and deployment alive until graded.
