# coding=utf-8
"""
Create Reddit dataset from Webis-TLDR-17 corpus (same source as TFDS Reddit builder).
Downloads corpus from Zenodo, randomly samples 50,000 records, keeps only id, text, subreddit.
Saves to backend/rag/data/reddit_50k.json for RAG build.
"""
from __future__ import annotations

import json
import random
import shutil
import sys
import zipfile
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

# Same URL as TensorFlow Datasets Reddit (webis-tldr-17)
_URL = "https://zenodo.org/record/1043504/files/corpus-webis-tldr-17.zip?download=1"
_TARGET_SIZE = 50_000
_DATA_DIR = Path(__file__).resolve().parent / "data"
_OUTPUT_JSON = _DATA_DIR / "reddit_50k.json"
_OUTPUT_CSV = _DATA_DIR / "reddit_50k.csv"


def reservoir_sample(stream, k, rng=None):
    """Yield k items uniformly at random from an iterator (reservoir sampling)."""
    rng = rng or random.Random()
    reservoir = []
    for i, item in enumerate(stream):
        if len(reservoir) < k:
            reservoir.append(item)
        else:
            j = rng.randrange(i + 1)
            if j < k:
                reservoir[j] = item
    return reservoir


def iter_jsonl(path):
    """Yield parsed dicts from JSONL file."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def record_to_row(d):
    """Extract id, text, subreddit. Use body or content for text; skip if missing."""
    text = (d.get("body") or d.get("content") or "").strip()
    if not text or len(text) < 10:
        return None
    row_id = d.get("id") or ""
    if not row_id:
        return None
    subreddit = (d.get("subreddit") or "").strip() or None
    return {"id": str(row_id), "text": text[:8000], "subreddit": subreddit}


def main():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = _DATA_DIR / "corpus-webis-tldr-17.zip"
    jsonl_path = _DATA_DIR / "corpus-webis-tldr-17.json"

    # Download zip if not present
    if not jsonl_path.exists():
        if not zip_path.exists():
            print("Downloading corpus from Zenodo...")
            r = requests.get(_URL, stream=True)
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            print("Downloaded.")
        print("Extracting...")
        extract_dir = _DATA_DIR / "corpus_extract"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)
        # Find the JSONL file (may be in a subdir)
        for p in extract_dir.rglob("*.json"):
            if p.stat().st_size > 1_000_000:  # expect large corpus file
                shutil.move(str(p), str(jsonl_path))
                break
        else:
            # Fallback: first .json in archive
            with zipfile.ZipFile(zip_path, "r") as z:
                for name in z.namelist():
                    if name.endswith(".json"):
                        with z.open(name) as src:
                            with open(jsonl_path, "wb") as dst:
                                dst.write(src.read())
                        break
        print("Extracted.")

    # Stream JSONL and reservoir sample 50k
    print("Sampling 50,000 records (reservoir sampling)...")
    rng = random.Random(42)
    reservoir = []
    n = 0
    for d in iter_jsonl(jsonl_path):
        row = record_to_row(d)
        if row is None:
            continue
        n += 1
        if len(reservoir) < _TARGET_SIZE:
            reservoir.append(row)
        else:
            j = rng.randrange(n)
            if j < _TARGET_SIZE:
                reservoir[j] = row
        if n % 50000 == 0 and n > 0:
            print(f"  ... seen {n} valid records")
    rows = reservoir
    print(f"Total records sampled: {len(rows)} (from {n} valid)")

    # Save JSON (for build_rag)
    with open(_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=0)
    print(f"Saved: {_OUTPUT_JSON}")

    # Save CSV (optional)
    import csv
    with open(_OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "text", "subreddit"])
        w.writeheader()
        w.writerows(rows)
    print(f"Saved: {_OUTPUT_CSV}")

    print("Done. Build RAG with: python -m rag.build_rag rag/data/reddit_50k.json")


if __name__ == "__main__":
    main()
