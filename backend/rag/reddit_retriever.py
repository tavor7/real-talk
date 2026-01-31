"""
RAG: Retrieve Reddit chunks for informal language patterns. Caches retrieved chunks.
"""
from typing import Any

# In-memory cache for retrieved chunks (optimization)
_chunk_cache: dict[str, list[dict]] = {}


def _embedding_dim() -> int:
    """Dimension for embeddings (must match Pinecone index). Default 1536; set EMBEDDING_DIMENSION=512 if index is 512."""
    import os
    d = os.environ.get("EMBEDDING_DIMENSION", "1536")
    try:
        return int(d)
    except ValueError:
        return 1536


def get_embedding(text: str, dimension: int | None = None) -> list[float]:
    """Get embedding for text (OpenAI or mock). dimension must match Pinecone index (512 or 1536)."""
    import os
    dim = dimension if dimension is not None else _embedding_dim()
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            base_url = os.environ.get("OPENAI_BASE_URL") or None
            client = OpenAI(api_key=api_key, base_url=base_url)
            kwargs = {"model": "text-embedding-3-small", "input": text}
            if dim != 1536:
                kwargs["dimensions"] = dim
            r = client.embeddings.create(**kwargs)
            return r.data[0].embedding
        except Exception:
            pass
    return [0.1] * dim


def retrieve(query: str, top_k: int = 5, use_cache: bool = True) -> list[dict[str, Any]]:
    """Retrieve Reddit chunks for query. Uses cache when use_cache=True."""
    if use_cache and query.strip() in _chunk_cache:
        return _chunk_cache[query.strip()]
    from db.pinecone import query_reddit
    emb = get_embedding(query)
    chunks = query_reddit(emb, top_k=top_k)
    if use_cache and query.strip():
        _chunk_cache[query.strip()] = chunks
    return chunks
