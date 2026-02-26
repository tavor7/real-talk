# RealTalk -- Language School AI Agent

An autonomous AI agent for language schools that simulates realistic, slang-based conversations. It adapts to the learner's proficiency level and uses RAG over Reddit data for authentic informal language patterns.

**Live demo:** Deployed on [Render](https://render.com) (see [Deployment](#deployment-render)).

## Team

| Name | Email |
|------|-------|
| Amit Tavor | amit.tavor@campus.technion.ac.il |
| Sagie Dekel | sagie.dekel@campus.technion.ac.il |
| Itay Nulman | itai.nulman@campus.technion.ac.il |

Group & batch order: **1_1**

## Project Structure

```
real-talk/
├── backend/
│   ├── agents/
│   │   ├── supervisor.py          # SupervisorAgent — orchestrates the full pipeline
│   │   ├── planner.py             # ProgramPlanner — Plan & Execute agent
│   │   ├── scenario_architect.py  # ScenarioArchitect — builds scenarios from RAG + profile
│   │   ├── conversation_partner.py# ConversationPartner — generates dialogue responses
│   │   ├── critic.py              # SystemCritic — reflection agent, decides end/continue
│   │   ├── user_evaluation.py     # UserEvaluation — ReAct agent, evaluates learner
│   │   └── llm_helper.py          # Shared LLM call utility, JSON parsing, CEFR helpers
│   ├── api/
│   │   └── routes.py              # FastAPI route definitions (all /api/* endpoints)
│   ├── db/
│   │   ├── supabase.py            # Supabase client — profiles, proficiency, summaries
│   │   └── pinecone.py            # Pinecone client — vector DB for RAG
│   ├── rag/
│   │   ├── reddit_retriever.py    # RAG retrieval with in-memory caching
│   │   ├── build_rag.py           # Script to embed and upsert data into Pinecone
│   │   ├── create_reddit_dataset.py # Downloads & samples 50k Reddit records
│   │   ├── clean_pinecone.py      # Utility to delete all vectors from Pinecone
│   │   ├── test_pinecone.py       # Connection and query test for Pinecone
│   │   └── data/                  # Reddit JSON/CSV datasets
│   ├── scripts/
│   │   └── clean_supabase.py      # Reset Supabase tables
│   ├── main.py                    # FastAPI app entry point
│   ├── cli.py                     # Command-line interface for terminal-based practice
│   ├── supabase_schema.sql        # SQL schema for all Supabase tables
│   └── requirements.txt           # Python dependencies
├── frontend/
│   ├── index.html                 # Web UI
│   ├── app.js                     # Frontend logic (API calls, chat, steps trace)
│   └── styles.css                 # Styling
├── assets/
│   └── architecture.png           # Architecture diagram (served by /api/model_architecture)
├── render.yaml                    # Render deployment configuration
└── README.md
```

## Architecture

The system uses a **multi-agent pipeline** orchestrated by the **SupervisorAgent**. Each sub-agent handles a specific concern, and the pipeline adapts between first and subsequent conversation turns to minimize LLM calls.

### Agent Modules

| Module | Agent Pattern | Role |
|--------|--------------|------|
| **SupervisorAgent** | Orchestrator | Routes the conversation flow, decides which agents to invoke, aggregates the final response |
| **ProgramPlanner** | Plan & Execute | Analyzes learner profile and scenario to produce a learning objective, conversation structure, key vocabulary, and difficulty adjustments |
| **RAGQueryRephraser** | Chain-of-Thought | Converts the scenario hint + plan into an optimized natural-language search query for Reddit retrieval |
| **ScenarioArchitect** | RAG-augmented | Designs a specific, immersive scenario description using the plan and retrieved Reddit examples |
| **ConversationPartner** | Generator | Produces natural conversational replies matching the scenario, learner level, and RAG style examples |
| **CriticGate** | Router / Gate | Lightweight LLM call that decides whether to invoke the full SystemCritic (runs from the 2nd turn onward) |
| **SystemCritic** | Reflection | When invoked, decides whether to end the conversation or continue with feedback for ConversationPartner |
| **UserEvaluation** | ReAct | Evaluates the learner's real-life English performance at the end of a conversation and generates a summary + LLM instructions for the next session |

### Pipeline Flow

**First turn** (scenario creation):

```
ProgramPlanner → RAGQueryRephraser → ScenarioArchitect → ConversationPartner
```

**Subsequent turns** (conversation):

```
CriticGate → [SystemCritic if needed] → ConversationPartner
```

**End of conversation** (user-initiated or Critic-triggered):

```
UserEvaluation → Save summary & LLM instructions to Supabase
```

### Optimization Strategies

- **Conditional agent invocation**: CriticGate prevents unnecessary Critic calls on most turns. The full SystemCritic only runs when the user appears to be ending or when conversation diverges.
- **Periodic Critic checks**: Every 3rd user message triggers a forced Critic run to ensure quality.
- **RAG caching**: Retrieved chunks are cached in-memory so repeated queries don't hit Pinecone/OpenAI embeddings again.
- **Prompt truncation**: `LLM_PROMPT_MAX_LENGTH` env var caps prompt sizes to control token usage.
- **Minimal context windows**: Only the last 4-8 messages are included in prompts (not the full history).
- **ANSWER extraction**: All agents use a Chain-of-Thought "think step by step... ANSWER: {json}" pattern. Only the final ANSWER section is parsed, so reasoning tokens are used for quality but not forwarded to downstream agents.

## Databases

### Supabase (Primary Database)

Stores user data and conversation history across sessions.

| Table | Purpose |
|-------|---------|
| `user_profiles` | 10 predefined learner profiles (name, CEFR level, goals, age group) |
| `proficiency` | Caches last scenario and summary per user (updated on conversation end) |
| `conversation_summaries` | Stores evaluation summaries and LLM instructions per profile (used for continuity across sessions) |
| `cli_sessions` | Temporary server-side conversation history for CLI users (deleted on conversation end) |

### Pinecone (Vector Database)

Stores embeddings of 50,000 Reddit comments (Webis-TLDR-17 corpus) for RAG retrieval. ScenarioArchitect queries Pinecone on every first turn to retrieve authentic informal language examples that seed the conversation scenario.

## API Endpoints

All endpoints are prefixed with `/api/`.

### A) `GET /api/team_info`

Returns student details.

```bash
curl http://localhost:8000/api/team_info
```

Response:

```json
{
  "group_batch_order_number": "1_1",
  "team_name": "RealTalk Team",
  "students": [
    {"name": "Amit Tavor", "email": "amit.tavor@campus.technion.ac.il"},
    {"name": "Sagie Dekel", "email": "sagie.dekel@campus.technion.ac.il"},
    {"name": "Itay Nulman", "email": "itai.nulman@campus.technion.ac.il"}
  ]
}
```

### B) `GET /api/agent_info`

Returns agent description, purpose, prompt templates, pipeline description, and full prompt examples with traced steps.

```bash
curl http://localhost:8000/api/agent_info
```

Response includes:
- `description` -- what the agent does
- `purpose` -- why it exists
- `prompt_template` -- suggested input format
- `agent_pipeline` -- ordered list of all modules in the pipeline
- `prompt_examples` -- two full worked examples with all steps (ProgramPlanner, RAGQueryRephraser, ScenarioArchitect, ConversationPartner)

### C) `GET /api/model_architecture`

Returns the architecture diagram as a PNG image.

```bash
curl http://localhost:8000/api/model_architecture -o architecture.png
```

- Content-Type: `image/png`
- All sub-module names in the diagram match the step names in `/api/execute` responses.

### D) `POST /api/execute`

Main entry point. Accepts a user prompt and returns the agent response with full traced steps.

**Input:**

```json
{
  "prompt": "User request here",
  "user_profile_id": "1",
  "scenario": "Coffee shop conversation",
  "conversation_history": [],
  "end_conversation": false,
  "generated_scenario": null,
  "session_id": null
}
```

Only `prompt` is required. All other fields are optional.

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | string (required) | The user's message |
| `user_profile_id` | string | Profile ID from `/api/user_profiles`. Defaults to first profile. |
| `scenario` | string | Scenario name or description. Defaults to "Casual conversation". |
| `conversation_history` | list | Previous messages as `[{"role": "user"/"assistant", "content": "..."}]` |
| `end_conversation` | bool | Set `true` to end and get evaluation summary |
| `generated_scenario` | dict | Scenario object from first turn (reused on subsequent turns) |
| `session_id` | string | CLI mode only: enables server-side history via Supabase |

**Success Response:**

```json
{
  "status": "ok",
  "error": null,
  "response": "Full agent response text...",
  "reply": "Plain message for conversation history",
  "generated_scenario": {"scenario": "..."},
  "steps": [
    {
      "module": "ProgramPlanner",
      "prompt": {"system": "...", "user": "..."},
      "response": "..."
    },
    {
      "module": "RAGQueryRephraser",
      "prompt": {"system": "...", "user": "..."},
      "response": "..."
    }
  ],
  "conversation_ended": false
}
```

**Error Response:**

```json
{
  "status": "error",
  "error": "Human-readable error description",
  "response": null,
  "reply": null,
  "generated_scenario": null,
  "steps": [],
  "conversation_ended": false
}
```

**Steps** is an array of every LLM call the agent made, in order. Each step contains:
- `module` -- the module name (matches the architecture diagram)
- `prompt` -- the full prompt sent to the LLM (`system` + `user`)
- `response` -- the full LLM response

### E) `GET /api/user_profiles`

Returns the list of 10 predefined user profiles from Supabase (or built-in defaults).

```bash
curl http://localhost:8000/api/user_profiles
```

## Frontend (Web UI)

The frontend is a single-page web app served at `/app/` with:

- **Profile selector** -- dropdown to pick one of 10 predefined learner profiles
- **Scenario selector** -- dropdown for 5 predefined scenarios, or free-text input for custom scenarios
- **"Run Agent" button** -- calls `POST /api/execute` to start the conversation
- **Chat interface** -- back-and-forth conversation with the agent, including conversation history
- **"Send" button** -- sends follow-up messages during the conversation
- **"End conversation" button** -- ends the conversation and displays evaluation summary
- **"Chat again" button** -- resets the UI for a new conversation
- **Steps trace panel** -- displays the full execution trace (module, prompt, response) for every LLM call
- **Request & Response details** -- shows the raw request fields and response fields for each API call
- **Loading indicator** -- visual feedback during API calls

### How to Use

1. Select a user profile (e.g., Alex, A2 level).
2. Choose a predefined scenario or type your own.
3. Click **Run Agent** to begin.
4. The agent talks **TO** you as a conversation partner in the scenario (e.g., a barista, a friend).
5. Reply in the chat; the agent adapts to your level and stays on topic.
6. Click **End conversation** to get an evaluation of your real-life English and tips for improvement. The summary and LLM instructions are saved to Supabase for your next session.
7. Click **Chat again** to start a new conversation.
8. Expand **Steps trace** to inspect full prompts and responses from each agent module.

## CLI (Command-Line Interface)

For terminal-based practice without a browser:

```bash
cd backend
python cli.py                              # default profile + default scenario
python cli.py --profile 2                  # pick profile by id
python cli.py --scenario "gaming"          # pick scenario by keyword
python cli.py --api https://your-render-url.onrender.com  # connect to deployed backend
```

Type your message and press Enter. Type `end`, `quit`, or `exit` to finish and receive your evaluation. Conversation history is stored server-side in Supabase for the session duration.

## User Profiles

10 predefined learner profiles with different CEFR levels and interests:

| ID | Name | Level | Goals | Age Group |
|----|------|-------|-------|-----------|
| 1 | Alex | A2 | gaming, streaming | 18-25 |
| 2 | Maria | B1 | travel, TikTok | 25-35 |
| 3 | Jordan | B2 | work meetings, slang | 30-40 |
| 4 | Sam | A1 | basics, memes | 16-22 |
| 5 | Casey | C1 | native-like informal | 28-35 |
| 6 | Riley | A2 | dating app, friends | 20-28 |
| 7 | Taylor | B1 | podcasts, Reddit | 22-30 |
| 8 | Morgan | B2 | gaming voice chat | 18-26 |
| 9 | Quinn | A2 | travel, casual chat | 25-35 |
| 10 | Jamie | B1 | social media, slang | 19-27 |

**CEFR Levels:**
- **A1/A2**: Beginner -- basic vocabulary, simple sentences
- **B1/B2**: Intermediate -- handles most everyday situations, some complex topics
- **C1/C2**: Advanced -- near-native fluency, complex topics

## Predefined Scenarios

5 predefined scenarios for quick start:

| ID | Name | Description |
|----|------|-------------|
| coffee | Casual chat at a coffee shop | Practice small talk and ordering |
| gaming | Arguing about a game with a friend | Practice gaming slang and friendly disagreements |
| party | Meeting someone at a party | Practice introductions and casual party conversation |
| streaming | Talking like a streamer to viewers | Practice streaming slang and viewer interaction |
| diner | Ordering food at a casual diner | Practice ordering food with casual slang |

Custom scenarios are also supported -- type any description and the agent will adapt.

## RAG (Reddit Data in Pinecone)

The RAG pipeline provides authentic informal language examples to the ScenarioArchitect. Data comes from the **Webis-TLDR-17** Reddit corpus (50,000 sampled records).

### Setup

1. **Create a Pinecone index** with dimension **512** (default) or 1536, metric: cosine.

2. **Create the dataset** (downloads from Zenodo, samples 50k records):
   ```bash
   cd backend
   python -m rag.create_reddit_dataset
   ```

3. **Build RAG** (embeds and upserts to Pinecone):
   ```bash
   cd backend
   python -m rag.build_rag rag/data/reddit_50k.json
   ```

4. **Test the connection:**
   ```bash
   cd backend
   python -m rag.test_pinecone
   ```

### How RAG is Used at Runtime

1. **RAGQueryRephraser** converts the scenario + plan into an optimized search query.
2. **ScenarioArchitect** calls `retrieve(query, top_k=1)` to get the most relevant Reddit chunk.
3. Retrieved chunks are included in the ScenarioArchitect prompt as examples of authentic speech.
4. The resulting scenario and RAG examples are passed to **ConversationPartner** so replies use a natural informal tone.

### Cleaning Pinecone

```bash
cd backend
python -m rag.clean_pinecone          # interactive confirmation
python -m rag.clean_pinecone --yes    # skip confirmation
```

## Supabase Setup

Tables should already be created. To recreate from scratch:

1. Go to [Supabase Dashboard](https://app.supabase.com) → Your Project → **SQL Editor** → **New query**
2. Paste the contents of `backend/supabase_schema.sql` and click **Run**
3. Verify in **Table Editor**: `user_profiles` (10 rows), `proficiency`, `conversation_summaries`

**Reset all conversation data:**

```bash
cd backend
python scripts/clean_supabase.py
# Or to also delete user_profiles:
python scripts/clean_supabase.py --include-profiles
```

## Environment Variables

Set these in `backend/.env`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | API key for LLM calls and embeddings (LLMod.ai / OpenAI) |
| `OPENAI_BASE_URL` | No | Custom API base URL (e.g., `https://api.llmod.ai/v1`). Omit for api.openai.com. |
| `OPENAI_MODEL` | No | Chat model name (default: `gpt-4o-mini`) |
| `OPENAI_EMBEDDING_MODEL` | No | Embedding model (default: `text-embedding-3-small`) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key (bypasses RLS). Preferred for backend. |
| `SUPABASE_ANON_KEY` | No | Alternative to service key (respects RLS) |
| `PINECONE_API_KEY` | Yes | Pinecone API key for RAG |
| `PINECONE_INDEX` | No | Pinecone index name (default: `reddit-informal`) |
| `EMBEDDING_DIMENSION` | No | Must match Pinecone index: `512` (default on Render) or `1536` |
| `LLM_PROMPT_MAX_LENGTH` | No | If set, truncates prompts before sending to LLM |
| `LLM_MAX_TOKENS` | No | If set, caps LLM response token count |
| `LLM_REQUEST_DELAY` | No | Delay (seconds) before each LLM call to avoid rate limits |
| `DEBUG_LLM` | No | Set to `1` to print raw LLM prompts and responses to stderr |

## Run Locally

```bash
cd backend
pip install -r requirements.txt
# Create backend/.env with the variables above
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Available URLs:**
- Frontend: http://localhost:8000/app/
- API docs (Swagger): http://localhost:8000/docs
- API base: http://localhost:8000/api/

## Deployment (Render)

The project includes a `render.yaml` for one-click deployment on [Render](https://render.com):

- **Service type:** Web service (Python)
- **Root directory:** `backend/`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Environment variables:** Set all required keys (OpenAI, Supabase, Pinecone) in the Render dashboard.

Keep the deployment active until graded.

## Conversation Flow Details

- **Agent role**: The agent talks **TO** the learner as a conversation partner (e.g., barista, friend, gamer). It never impersonates the learner.
- **Conversation continuity**: When a conversation ends, the evaluation summary and LLM instructions are saved to Supabase. On the next conversation with the same profile, the agent loads previous summaries (up to 5) and the latest instructions for context.
- **Critic behavior**: From the 2nd turn, CriticGate runs to detect farewell phrases or topic drift. If triggered, SystemCritic decides whether to end or continue. Every 3rd user message forces a Critic check regardless.
- **UserEvaluation focus**: Evaluates only the learner's messages in terms of real-life daily English -- naturalness, communicativeness, and practical effectiveness, not just grammar.

## Debugging

**Enable debug logging:**
```bash
cd backend
DEBUG_LLM=1 uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

This prints full LLM prompts and responses to stderr for every module.

**Common issues:**
- Empty LLM responses: Check API key, model name, and rate limits. The system retries up to 3 times and falls back to mock responses.
- RAG not working: Verify `PINECONE_API_KEY`, `PINECONE_INDEX`, and `EMBEDDING_DIMENSION` match your index. Run `python -m rag.test_pinecone`.
- Supabase connection issues: Verify `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set correctly.

## Tech Stack

- **Backend:** Python, FastAPI, Uvicorn
- **LLM Provider:** LLMod.ai (OpenAI-compatible API)
- **Primary Database:** Supabase (PostgreSQL)
- **Vector Database:** Pinecone
- **Embeddings:** OpenAI `text-embedding-3-small` (512 or 1536 dimensions)
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **Deployment:** Render
- **RAG Corpus:** Webis-TLDR-17 Reddit dataset (50k sampled records)
