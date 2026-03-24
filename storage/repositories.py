from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from sqlite3 import Row
from typing import Any

from runtime.schemas import MemoryRecord, MemorySearchResult, ShortTermSnapshot
from storage.db import db_session


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_memory(row: Row) -> MemoryRecord:
    return MemoryRecord(
        memory_id=row["id"],
        memory_type=row["memory_type"],
        title=row["title"],
        summary=row["summary"],
        content=row["content"],
        source=row["source"],
        fingerprint=row["fingerprint"],
        quality_score=row["quality_score"],
        created_at=row["created_at"],
    )


class TaskRepository:
    def create_task(self, task: str) -> int:
        now = _now()
        with db_session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks(task, status, current_round, final_answer, checker_passed, checker_score, created_at, updated_at)
                VALUES (?, 'running', 0, '', 0, 0, ?, ?)
                """,
                (task, now, now),
            )
            return int(cursor.lastrowid)

    def update_task(self, task_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [task_id]
        with db_session() as conn:
            conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", values)

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with db_session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]


class MessageRepository:
    def append_message(self, task_id: int, role: str, stage: str, content: str) -> None:
        with db_session() as conn:
            conn.execute(
                "INSERT INTO messages(task_id, role, stage, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, role, stage, content, _now()),
            )

    def list_messages(self, task_id: int) -> list[dict[str, Any]]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            ).fetchall()
            return [dict(row) for row in rows]


class WorkerRunRepository:
    def create_run(
        self,
        task_id: int,
        round_index: int,
        worker_name: str,
        instruction: str,
        status: str,
        summary: str,
        traces: list[str],
    ) -> None:
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO worker_runs(task_id, round_index, worker_name, instruction, status, summary, traces_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, round_index, worker_name, instruction, status, summary, json.dumps(traces, ensure_ascii=False), _now()),
            )

    def list_runs(self, task_id: int) -> list[dict[str, Any]]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM worker_runs WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            ).fetchall()
            items: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["traces"] = json.loads(item.pop("traces_json"))
                items.append(item)
            return items


class MemoryRepository:
    def get_by_fingerprint(self, fingerprint: str) -> MemoryRecord | None:
        with db_session() as conn:
            row = conn.execute("SELECT * FROM memories WHERE fingerprint = ?", (fingerprint,)).fetchone()
            return _row_to_memory(row) if row else None

    def list_memories(self, limit: int = 50) -> list[MemoryRecord]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [_row_to_memory(row) for row in rows]

    def upsert_memory(
        self,
        *,
        memory_type: str,
        title: str,
        summary: str,
        content: str,
        source: str,
        fingerprint: str,
        quality_score: int,
        embedding: list[float] | None,
    ) -> MemoryRecord:
        existing = self.get_by_fingerprint(fingerprint)
        now = _now()
        embedding_json = json.dumps(embedding or [])
        with db_session() as conn:
            if existing:
                conn.execute(
                    """
                    UPDATE memories
                    SET title = ?, summary = ?, content = ?, source = ?, quality_score = ?, embedding_json = ?, updated_at = ?
                    WHERE fingerprint = ?
                    """,
                    (title, summary, content, source, quality_score, embedding_json, now, fingerprint),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO memories(memory_type, title, summary, content, source, fingerprint, quality_score, embedding_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (memory_type, title, summary, content, source, fingerprint, quality_score, embedding_json, now, now),
                )
                memory_id = int(cursor.lastrowid)
                conn.execute(
                    "INSERT OR REPLACE INTO memory_fingerprints(fingerprint, memory_id, source, created_at) VALUES (?, ?, ?, ?)",
                    (fingerprint, memory_id, source, now),
                )
        return self.get_by_fingerprint(fingerprint)  # type: ignore[return-value]

    def search_memories(self, query_embedding: list[float], limit: int = 4) -> list[MemorySearchResult]:
        def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
            if not vec_a or not vec_b or len(vec_a) != len(vec_b):
                return 0.0
            numerator = sum(a * b for a, b in zip(vec_a, vec_b))
            norm_a = sum(a * a for a in vec_a) ** 0.5
            norm_b = sum(b * b for b in vec_b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return numerator / (norm_a * norm_b)

        with db_session() as conn:
            rows = conn.execute("SELECT * FROM memories ORDER BY updated_at DESC").fetchall()

        results: list[MemorySearchResult] = []
        for row in rows:
            embedding = json.loads(row["embedding_json"] or "[]")
            score = cosine_similarity(query_embedding, embedding)
            if score <= 0:
                continue
            results.append(
                MemorySearchResult(
                    memory_id=row["id"],
                    summary=row["summary"],
                    score=score,
                    memory_type=row["memory_type"],
                    source=row["source"],
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:limit]

    def memory_stats(self) -> dict[str, Any]:
        with db_session() as conn:
            total = conn.execute("SELECT COUNT(*) AS count FROM memories").fetchone()["count"]
            by_type_rows = conn.execute(
                "SELECT memory_type, COUNT(*) AS count FROM memories GROUP BY memory_type ORDER BY count DESC"
            ).fetchall()
        return {
            "total_memories": total,
            "by_type": [{"memory_type": row["memory_type"], "count": row["count"]} for row in by_type_rows],
        }


class ArtifactRepository:
    def add_artifact(self, task_id: int, artifact_type: str, path: str) -> None:
        with db_session() as conn:
            conn.execute(
                "INSERT INTO run_artifacts(task_id, artifact_type, path, created_at) VALUES (?, ?, ?, ?)",
                (task_id, artifact_type, path, _now()),
            )

    def list_artifacts(self, task_id: int) -> list[dict[str, Any]]:
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM run_artifacts WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            ).fetchall()
            return [dict(row) for row in rows]


class SnapshotRepository:
    def serialize_snapshot(self, snapshot: ShortTermSnapshot) -> dict[str, Any]:
        return asdict(snapshot)
