from __future__ import annotations

from datetime import UTC, datetime

from ingest import get_embeddings
from memory.dedup import build_fingerprint
from memory.retrieval import search_long_term_memories
from runtime.schemas import CheckerResult, MemoryRecord, MemorySearchResult
from storage.db import init_db
from storage.repositories import MemoryRepository
from utils import Settings


def _embedding_ready_text(content: str, max_chars: int = 320) -> str:
    normalized = " ".join(content.split())
    return normalized[:max_chars]


def _safe_embed_text(embeddings, content: str) -> list[float]:
    for max_chars in (320, 220, 140):
        try:
            return embeddings.embed_query(_embedding_ready_text(content, max_chars=max_chars))
        except Exception as exc:
            if "less than 512 tokens" not in str(exc):
                raise
    return embeddings.embed_query(_embedding_ready_text(content, max_chars=100))


class LongTermMemoryManager:
    def __init__(self, settings: Settings):
        init_db()
        self.settings = settings
        self.repository = MemoryRepository()

    def search(self, query: str, limit: int = 4) -> list[MemorySearchResult]:
        return search_long_term_memories(query, self.settings, limit=limit)

    def maybe_store_high_value_result(
        self,
        *,
        task: str,
        final_answer: str,
        checker: CheckerResult,
        source: str,
        task_pattern: str | None = None,
        research_note: str | None = None,
    ) -> list[MemoryRecord]:
        if not checker.passed or checker.score < 70 or not final_answer.strip():
            return []

        embeddings = get_embeddings(self.settings)
        memory_specs = [
            {
                "memory_type": "artifact_summary",
                "title": task[:80],
                "summary": final_answer[:280],
                "content": final_answer,
            }
        ]

        if research_note and research_note.strip():
            memory_specs.append(
                {
                    "memory_type": "research_note",
                    "title": f"研究结论: {task[:60]}",
                    "summary": research_note[:280],
                    "content": research_note,
                }
            )

        if task_pattern and task_pattern.strip():
            memory_specs.append(
                {
                    "memory_type": "task_pattern",
                    "title": f"任务模式: {task[:60]}",
                    "summary": task_pattern[:280],
                    "content": task_pattern,
                }
            )

        records: list[MemoryRecord] = []
        for spec in memory_specs:
            fingerprint = build_fingerprint(f"{spec['memory_type']}\n{task}\n{spec['content']}")
            embedding = _safe_embed_text(embeddings, spec["content"])
            records.append(
                self.repository.upsert_memory(
                    memory_type=spec["memory_type"],
                    title=spec["title"],
                    summary=spec["summary"],
                    content=spec["content"],
                    source=source,
                    fingerprint=fingerprint,
                    quality_score=checker.score,
                    embedding=embedding,
                )
            )
        return records

    def list_memories(self, limit: int = 50) -> list[MemoryRecord]:
        return self.repository.list_memories(limit=limit)

    def stats(self) -> dict:
        return self.repository.memory_stats()
