# RAG: Reddit-style data for informal language

The app uses Pinecone to store embeddings of informal/slang text. At runtime, ScenarioArchitect retrieves similar chunks to seed dialogue.

## What you need

1. **Pinecone index**  
   - Create an index in [Pinecone Console](https://app.pinecone.io) (or via API).  
   - **Dimension:** **512** (build script default) or **1536**. Use `--embedding-dimension 1536` if your index is 1536-dim.  
   - Metric: cosine.

2. **Reddit-style data file**  
   - One row per “chunk” (e.g. one Reddit comment or post, or one short paragraph).  
   - Each row must have a unique **id** and the **text** to embed.

## Data format

### Option A: CSV

- Header row with at least: `id`, `text`.  
- Optional: `body` (used as text if `text` is missing), `subreddit`, etc.

Example `reddit.csv`:

```csv
id,text,subreddit
1,"Bro that was so clutch, we totally carried.",gaming
2,"Just ordered a cold brew, lowkey addicted.",coffee
```

### Option B: JSON

- A **JSON array** of objects.  
- Each object must have **text** (or `body` or `content`) and ideally **id**.  
- Optional: `subreddit`, etc.

Example `reddit.json`:

```json
[
  {"id": "1", "text": "Bro that was so clutch.", "subreddit": "gaming"},
  {"id": "2", "text": "Just ordered a cold brew, lowkey addicted.", "subreddit": "coffee"}
]
```

A small sample file is at **`rag/data/sample_reddit.json`** for testing.

## How to run the RAG build

From the **backend** directory (so `rag` and `db` are importable):

```bash
cd backend

# Load .env (OPENAI_API_KEY, OPENAI_BASE_URL, PINECONE_*)
# Then run the script with your data file:

python -m rag.build_rag rag/data/sample_reddit.json
```

Options:

- `--namespace NAME` – Pinecone namespace (default: default).
- `--batch N` – Batch size for embedding + upsert (default: 50).
- `--dry-run` – Only load the file and print row count; no API calls.

Examples:

```bash
# Test with sample data (no Pinecone/OpenAI needed for --dry-run)
python -m rag.build_rag rag/data/sample_reddit.json --dry-run

# Build RAG from your CSV
python -m rag.build_rag /path/to/reddit.csv

# Use a namespace
python -m rag.build_rag rag/data/sample_reddit.json --namespace informal
```

## Where to get Reddit data

- **Kaggle:** e.g. “Reddit Comments”, “Reddit Posts” – download CSV/JSON and ensure columns include something you can map to `id` and `text` (or `body`).  
- **Reddit API:** if you collect data yourself, export as CSV or JSON in the format above.  
- **Start small:** use `rag/data/sample_reddit.json` to verify the pipeline, then replace with a larger file.

After a successful run, the app’s RAG retrieval (e.g. in ScenarioArchitect) will use these vectors when `PINECONE_API_KEY` and `PINECONE_INDEX` (and optional `PINECONE_HOST`) are set in `.env`.
