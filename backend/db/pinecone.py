"""
Pinecone: Vector DB for Reddit embeddings (RAG).
"""
import os
from typing import Any

_index = None


def get_index():
    global _index
    if _index is None:
        api_key = os.environ.get("PINECONE_API_KEY")
        index_name = os.environ.get("PINECONE_INDEX", "reddit-informal")
        if api_key:
            from pinecone import Pinecone
            pc = Pinecone(api_key=api_key)
            # SDK expects index NAME (e.g. "real-talk"); it fetches the host via API. Do not pass PINECONE_HOST here.
            _index = pc.Index(index_name)
    return _index


def query_reddit(query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    """Query Reddit chunks by embedding. Returns list of {text, metadata}."""
    idx = get_index()
    if not idx:
        return []
    try:
        r = idx.query(vector=query_embedding, top_k=top_k, include_metadata=True)
        # SDK v3 returns QueryResponse with .matches (ScoredVector objects), not plain dicts
        matches = []
        if hasattr(r, "matches"):
            matches = r.matches or []
        elif isinstance(r, dict):
            matches = r.get("matches") or []
        out = []
        for m in matches:
            if isinstance(m, dict):
                meta = m.get("metadata") or {}
            else:
                meta = getattr(m, "metadata", None) or {}
            text = meta.get("text", "") if isinstance(meta, dict) else getattr(meta, "text", "")
            out.append({"text": text, "metadata": meta})
        return out
    except Exception:
        return []


def upsert_vectors(vectors: list[tuple[str, list[float], dict[str, Any]]], namespace: str = "") -> None:
    """
    Upsert vectors to Pinecone. Each item is (id, embedding_values, metadata).
    Metadata should include "text" so RAG retrieval can return it.
    """
    idx = get_index()
    if not idx:
        raise RuntimeError("Pinecone index not available; set PINECONE_API_KEY and ensure index exists.")
    kwargs = {"vectors": vectors}
    if namespace:
        kwargs["namespace"] = namespace
    try:
        idx.upsert(**kwargs)
    except Exception as e:
        err = str(e)
        if "dimension" in err.lower() or "1536" in err or "512" in err:
            raise RuntimeError(
                "Pinecone index dimension doesn't match embeddings. "
                "Your index is 512-dim: add EMBEDDING_DIMENSION=512 to backend/.env and run again. "
                "Or create a new index with dimension 1536 (for default text-embedding-3-small)."
            ) from e
        raise
