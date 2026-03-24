from __future__ import annotations

import json

from langchain_core.tools import tool

from memory.long_term import LongTermMemoryManager
from memory.short_term import ShortTermMemoryManager
from utils import Settings


def build_memory_tools(settings: Settings, short_term: ShortTermMemoryManager, task_id: int | None = None):
    long_term = LongTermMemoryManager(settings)

    @tool
    def search_long_term_memory(query: str, top_k: int = 4) -> str:
        """检索长期记忆，返回相关历史结论、偏好或高价值结果。"""
        results = long_term.search(query, limit=top_k)
        return json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2)

    @tool
    def inspect_runtime_context() -> str:
        """查看当前任务的短期上下文快照。"""
        if task_id is None:
            return json.dumps({"detail": "当前运行时未绑定 task_id。"}, ensure_ascii=False, indent=2)
        snapshot = short_term.get_context_snapshot(task_id)
        return json.dumps(snapshot.__dict__, ensure_ascii=False, indent=2)

    return [search_long_term_memory, inspect_runtime_context]
