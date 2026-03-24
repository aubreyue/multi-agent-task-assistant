from __future__ import annotations

from collections import defaultdict

from memory.compression import compress_history
from runtime.constants import DEFAULT_CONTEXT_CHAR_BUDGET, DEFAULT_SLIDING_WINDOW_SIZE
from runtime.schemas import ShortTermSnapshot
from storage.db import init_db
from storage.repositories import MessageRepository
from utils import Settings


class ShortTermMemoryManager:
    def __init__(self, settings: Settings):
        init_db()
        self.settings = settings
        self.messages = MessageRepository()
        self._compressed_history: dict[int, str] = defaultdict(str)

    def append_short_term_event(self, task_id: int, role: str, stage: str, content: str) -> None:
        self.messages.append_message(task_id, role, stage, content)

    def build_runtime_context(self, task_id: int, role: str) -> str:
        snapshot = self.get_context_snapshot(task_id)
        parts = [
            f"当前角色: {role}",
            "固定上下文:",
            "\n".join(f"- {item}" for item in snapshot.pinned_context) or "- 无",
            "最近事件:",
            "\n".join(f"- {item}" for item in snapshot.recent_events) or "- 无",
        ]
        if snapshot.compressed_history:
            parts.extend(["压缩历史:", snapshot.compressed_history])
        return "\n".join(parts)

    def compress_context_if_needed(self, task_id: int) -> ShortTermSnapshot:
        snapshot = self.get_context_snapshot(task_id)
        if snapshot.token_estimate <= DEFAULT_CONTEXT_CHAR_BUDGET:
            return snapshot

        older_events = snapshot.recent_events[:-DEFAULT_SLIDING_WINDOW_SIZE // 2]
        compressed = compress_history("\n".join(older_events), self.settings) if older_events else ""
        self._compressed_history[task_id] = compressed
        return self.get_context_snapshot(task_id)

    def get_context_snapshot(self, task_id: int) -> ShortTermSnapshot:
        messages = self.messages.list_messages(task_id)
        pinned_context: list[str] = []
        recent_events: list[str] = []

        for item in messages:
            label = f"{item['role']}[{item['stage']}]: {item['content']}"
            if item["stage"] in {"user_task", "master_summary", "checker_feedback", "criteria"}:
                pinned_context.append(label)
            else:
                recent_events.append(label)

        recent_events = recent_events[-DEFAULT_SLIDING_WINDOW_SIZE:]
        compressed_history = self._compressed_history.get(task_id, "")
        token_estimate = len("\n".join(pinned_context + recent_events + ([compressed_history] if compressed_history else [])))
        return ShortTermSnapshot(
            task_id=task_id,
            pinned_context=pinned_context[-6:],
            recent_events=recent_events,
            compressed_history=compressed_history,
            token_estimate=token_estimate,
            compression_applied=bool(compressed_history),
        )
