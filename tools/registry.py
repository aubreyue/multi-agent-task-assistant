from __future__ import annotations

import asyncio
from typing import Any

from memory.short_term import ShortTermMemoryManager
from tools.export_tools import build_export_tools
from tools.mcp_tools import load_mcp_tools
from tools.memory_tools import build_memory_tools
from tools.rag_tools import build_rag_tools
from tools.search_tools import build_search_tools
from utils import Settings


class ToolRegistry:
    def __init__(self, settings: Settings, short_term: ShortTermMemoryManager, task_id: int | None = None):
        self.settings = settings
        self.short_term = short_term
        self.task_id = task_id

    async def load_all_tools(self) -> list[Any]:
        mcp_tools = await load_mcp_tools()
        return [
            *build_rag_tools(self.settings),
            *build_search_tools(),
            *build_export_tools(),
            *build_memory_tools(self.settings, self.short_term, task_id=self.task_id),
            *mcp_tools,
        ]

    def load_all_tools_sync(self) -> list[Any]:
        return asyncio.run(self.load_all_tools())
