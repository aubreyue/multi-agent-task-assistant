from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from utils import BASE_DIR


async def load_mcp_tools() -> list[Any]:
    server_path = Path(BASE_DIR) / "mcp_server.py"
    client = MultiServerMCPClient(
        {
            "knowledge_base": {
                "transport": "stdio",
                "command": sys.executable,
                "args": ["-u", str(server_path)],
                "cwd": str(BASE_DIR),
            }
        }
    )
    return await client.get_tools()
