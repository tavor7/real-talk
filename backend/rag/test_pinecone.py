# coding=utf-8
"""
Test Pinecone connection and index for RAG.
Run from backend/ with: python -m rag.test_pinecone
Loads .env from backend/ so PINECONE_API_KEY and PINECONE_INDEX are set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env from backend/
_backend = Path(__file__).resolve().parent.parent
_env = _backend / ".env"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))


def main():
    api_key = (os.environ.get("PINECONE_API_KEY") or "").strip()
    index_name = (os.environ.get("PINECONE_INDEX") or "").strip()

    if not api_key:
        print("FAIL: PINECONE_API_KEY not set (add to backend/.env)")
        sys.exit(1)
    if not index_name:
        print("FAIL: PINECONE_INDEX not set (add to backend/.env)")
        sys.exit(1)

    print("Testing Pinecone connection...")
    print(f"  PINECONE_INDEX={index_name}")

    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=api_key)
        idx = pc.Index(index_name)
    except Exception as e:
        print(f"FAIL: Could not create index client: {e}")
        sys.exit(1)

    # Describe index (if supported)
    try:
        stats = idx.describe_index_stats()
        print("  describe_index_stats:", stats)
    except Exception as e:
        print("  describe_index_stats not available:", e)

    # Query with a dummy vector (dimension must match index: 512 or 1536)
    dim = 512
    if os.environ.get("EMBEDDING_DIMENSION"):
        try:
            dim = int(os.environ["EMBEDDING_DIMENSION"])
        except ValueError:
            pass
    dummy = [0.1] * dim
    try:
        r = idx.query(vector=dummy, top_k=2, include_metadata=True)
        matches = r.get("matches") or []
        print(f"  query (top_k=2): {len(matches)} matches")
        for i, m in enumerate(matches):
            meta = (m.get("metadata") or {}) if isinstance(m, dict) else {}
            text = (meta.get("text") or "")[:60]
            print(f"    [{i}] id={m.get('id')} text={text!r}...")
    except Exception as e:
        print(f"  query failed: {e}")

    print("Pinecone test done.")


if __name__ == "__main__":
    main()
