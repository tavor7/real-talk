"""
Build RAG: load Reddit-style data (CSV or JSON), embed with OpenAI, upsert to Pinecone.
Run from backend/ with: python -m rag.build_rag <path_to_data>
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

# Load .env from backend/
_backend = Path(__file__).resolve().parent.parent
_env = _backend / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

# Ensure backend is on path
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

# Embedding dimension for text-embedding-3-small
EMBED_DIM = 1536
BATCH_SIZE = 50  # Pinecone and API friendly


def load_data(path: str) -> list[dict]:
    """Load rows with 'id' and 'text' from CSV or JSON."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    rows = []
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                text = (row.get("text") or row.get("body") or "").strip()
                if not text:
                    continue
                rows.append({
                    "id": (row.get("id") or str(len(rows))).strip() or str(len(rows)),
                    "text": text[:8000],
                    "subreddit": row.get("subreddit", "").strip() or None,
                    **{k: v for k, v in row.items() if k not in ("id", "text", "body", "subreddit")},
                })
    elif path.suffix.lower() == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON file must be a list of items")
        for i, item in enumerate(data):
            if isinstance(item, dict):
                text = (item.get("text") or item.get("body") or item.get("content") or "").strip()
                row_id = str(item.get("id", i))
            else:
                text = str(item).strip()
                row_id = str(i)
            if not text:
                continue
            rows.append({"id": row_id, "text": text[:8000]})
    else:
        raise ValueError("Supported formats: .csv, .json")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Build RAG: embed Reddit-style data and upsert to Pinecone")
    parser.add_argument("data_path", help="Path to CSV or JSON file (must have 'id' and 'text' columns/fields)")
    parser.add_argument("--namespace", default="", help="Pinecone namespace (default: default)")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help="Batch size for upsert")
    parser.add_argument("--embedding-dimension", type=int, default=512, help="Pinecone index dimension (default: 512). Use 1536 for default text-embedding-3-small index.")
    parser.add_argument("--dry-run", action="store_true", help="Load and print row count only, no embed/upsert")
    args = parser.parse_args()

    embed_dim = args.embedding_dimension
    os.environ["EMBEDDING_DIMENSION"] = str(embed_dim)

    rows = load_data(args.data_path)
    print(f"Loaded {len(rows)} rows from {args.data_path}")

    if args.dry_run:
        for i, r in enumerate(rows[:3]):
            print(f"  [{i}] id={r['id']} text={r['text'][:80]}...")
        if len(rows) > 3:
            print(f"  ... and {len(rows) - 3} more")
        return

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY (and optionally OPENAI_BASE_URL) in backend/.env")
        sys.exit(1)

    from rag.reddit_retriever import get_embedding
    from db.pinecone import upsert_vectors

    for start in range(0, len(rows), args.batch):
        batch = rows[start : start + args.batch]
        vectors = []
        for r in batch:
            emb = get_embedding(r["text"], dimension=embed_dim)
            meta = {"text": r["text"]}
            if r.get("subreddit"):
                meta["subreddit"] = str(r["subreddit"])[:200]
            vectors.append((r["id"], emb, meta))
        upsert_vectors(vectors, namespace=args.namespace)
        print(f"Upserted {len(vectors)} vectors (rows {start + 1}–{start + len(vectors)})")
    print("Done.")


if __name__ == "__main__":
    main()
