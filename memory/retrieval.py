from __future__ import annotations

from ingest import get_embeddings
from runtime.constants import DEFAULT_MEMORY_SEARCH_K
from runtime.schemas import MemorySearchResult
from storage.repositories import MemoryRepository
from utils import Settings


def _embedding_ready_text(content: str, max_chars: int = 320) -> str:
    normalized = " ".join(content.split())
    return normalized[:max_chars]


def _safe_embed_query(embeddings, content: str) -> list[float]:
    for max_chars in (320, 220, 140):
        try:
            return embeddings.embed_query(_embedding_ready_text(content, max_chars=max_chars))
        except Exception as exc:
            if "less than 512 tokens" not in str(exc):
                raise
    return embeddings.embed_query(_embedding_ready_text(content, max_chars=100))


def search_long_term_memories(query: str, settings: Settings, limit: int = DEFAULT_MEMORY_SEARCH_K) -> list[MemorySearchResult]:
    embeddings = get_embeddings(settings)
    query_embedding = _safe_embed_query(embeddings, query)
    repository = MemoryRepository()
    return repository.search_memories(query_embedding, limit=limit)
