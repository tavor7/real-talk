# coding=utf-8
"""
Clean Pinecone index: delete all vectors (optionally in a namespace).
Run from backend/: python -m rag.clean_pinecone [--namespace NAME] [--yes]
Loads .env from backend/ for PINECONE_API_KEY and PINECONE_INDEX.
"""
from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Delete all vectors in Pinecone index (clean for fresh RAG build)")
    parser.add_argument("--namespace", default="", help="Namespace to clear (default: default/empty namespace)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    api_key = (os.environ.get("PINECONE_API_KEY") or "").strip()
    index_name = (os.environ.get("PINECONE_INDEX") or "").strip()

    if not api_key:
        print("FAIL: PINECONE_API_KEY not set (add to backend/.env)")
        sys.exit(1)
    if not index_name:
        print("FAIL: PINECONE_INDEX not set (add to backend/.env)")
        sys.exit(1)

    namespace = (args.namespace or "").strip()
    ns_label = f"namespace {namespace!r}" if namespace else "default namespace"

    if not args.yes:
        print(f"This will DELETE ALL vectors in index {index_name!r} ({ns_label}).")
        try:
            confirm = input("Type 'yes' to continue: ").strip().lower()
        except EOFError:
            confirm = ""
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    print(f"Connecting to index {index_name!r}...")
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=api_key)
        idx = pc.Index(index_name)
    except Exception as e:
        print(f"FAIL: Could not create index client: {e}")
        sys.exit(1)

    kwargs = {"delete_all": True}
    if namespace:
        kwargs["namespace"] = namespace

    try:
        idx.delete(**kwargs)
        print(f"Done. All vectors deleted in {ns_label}.")
    except TypeError:
        # Some SDK versions use different param name
        try:
            idx.delete(deleteAll=True, **(dict(namespace=namespace) if namespace else {}))
            print(f"Done. All vectors deleted in {ns_label}.")
        except Exception as e:
            print(f"FAIL: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
