# RAG: Reddit-style data for informal language

The app uses Pinecone to store embeddings of informal/slang text. At runtime, ScenarioArchitect retrieves similar chunks to seed dialogue.

## What you need

1. **Pinecone index**  
   - Create an index in [Pinecone Console](https://app.pinecone.io) (or via API).  
   - **Dimension:** **512** (build script default) or **1536**. Use `--embedding-dimension 1536` if your index is 1536-dim.  
   - Metric: cosine.

2. **Reddit-style data file**  
   - One row per “chunk” (e.g. one Reddit comment or post).  
   - Each row must have a unique **id** and **text** to embed.

---

## Reddit Webis-TLDR-17 dataset (50k records)

The project can use the **Webis-TLDR-17** Reddit corpus (same source as [TensorFlow Datasets Reddit](https://github.com/tensorflow/datasets/blob/master/tensorflow_datasets/summarization/reddit.py)). The script downloads the corpus from Zenodo, randomly samples **50,000** records, keeps only **id**, **text** (from `body` or `content`), and **subreddit**, and saves them in the project.

### 1. Create the dataset (run once)

From the **backend** directory:

```bash
cd backend
pip install requests   # if not already installed
python -m rag.create_reddit_dataset
```

This will:

- Download `corpus-webis-tldr-17.zip` from Zenodo (if not already in `rag/data/`).
- Extract the JSONL corpus.
- Randomly sample 50,000 records (reservoir sampling, seed=42).
- Drop all columns except **id**, **text**, **subreddit**.
- Save:
  - **`rag/data/reddit_50k.json`** – for the RAG build script.
  - **`rag/data/reddit_50k.csv`** – optional.

### 2. Build RAG from the 50k dataset

After the dataset is created:

```bash
cd backend
python -m rag.build_rag rag/data/reddit_50k.json
```

Use `--embedding-dimension 512` if your Pinecone index is 512-dim (default). For a large file, the script batches embeddings and upserts (default batch size 50). To use a custom namespace:

```bash
python -m rag.build_rag rag/data/reddit_50k.json --namespace reddit50k
```

---

## Cleaning Pinecone (delete all vectors)

To remove all vectors from your index (e.g. before a fresh RAG build):

```bash
cd backend
python -m rag.clean_pinecone
```

You will be prompted to type `yes` to confirm. To skip the prompt:

```bash
python -m rag.clean_pinecone --yes
```

To clear only a specific namespace:

```bash
python -m rag.clean_pinecone --namespace reddit50k --yes
```

---

## Testing Pinecone

To verify your Pinecone index and env vars without running the full RAG build:

```bash
cd backend
python -m rag.test_pinecone
```

This checks:

- `PINECONE_API_KEY` and `PINECONE_INDEX` (from `.env`).
- Index connection and optional `describe_index_stats`.
- A single query with a dummy vector (dimension from `EMBEDDING_DIMENSION` or 512).

---

## Data format (generic)

### Option A: CSV

- Header: `id`, `text` (or `body`). Optional: `subreddit`.
- Example: `id,text,subreddit`

### Option B: JSON

- A **JSON array** of objects with **id** and **text** (or **body** / **content**). Optional: **subreddit**.

A small sample is at **`rag/data/sample_reddit.json`** for quick tests.

---

## How to run the RAG build (generic)

From the **backend** directory:

```bash
cd backend
python -m rag.build_rag rag/data/sample_reddit.json
```

Options:

- **`--embedding-dimension 512`** (default) or **1536** – must match your Pinecone index.
- **`--namespace NAME`** – Pinecone namespace.
- **`--batch N`** – batch size (default 50).
- **`--dry-run`** – only load and print row count; no API calls.

Examples:

```bash
# Dry run (no API calls)
python -m rag.build_rag rag/data/sample_reddit.json --dry-run

# Build from 50k dataset
python -m rag.build_rag rag/data/reddit_50k.json

# 1536-dim index
python -m rag.build_rag rag/data/reddit_50k.json --embedding-dimension 1536
```

After a successful run, the app’s RAG retrieval (ScenarioArchitect) will use these vectors when `PINECONE_API_KEY`, `PINECONE_INDEX`, and optionally `EMBEDDING_DIMENSION` are set in `.env`.
