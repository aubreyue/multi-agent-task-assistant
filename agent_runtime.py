from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from ingest import list_supported_files, vectorstore_exists
from qa_chain import (
    answer_question,
    build_context_preview,
    build_source_labels,
    get_chat_model,
    retrieve_documents,
    save_markdown,
)
from utils import BASE_DIR, Settings
from web_tools import format_web_results, search_web


AGENT_SYSTEM_PROMPT = """
你是一个基于 LangChain 构建的中文学习资料智能助理，负责帮助用户围绕课程讲义、论文、技术文档和个人笔记完成学习、复习和研究任务。

你的工作方式：
1. 优先使用工具，不要凭空回答。
2. 处理学习任务时，优先检查本地学习资料、MCP 工具和检索结果。
3. 若用户询问“最新/最近/当前/今天”等时效性信息，或当前学习资料不足以回答，应主动联网搜索。
4. 回答中尽量区分“学习资料依据”和“联网补充依据”，并说明来源。
5. 如果发现向量库尚未建立，应提示用户先构建，或调用可用工具进行重建。
6. 输出保持结构化、简洁、适合学习者理解，可适当整理为提纲、知识点或复习笔记。
"""


def build_agent(settings: Settings):
    @tool
    def rag_answer(question: str) -> str:
        """基于本地学习资料检索并生成答案，适合课程讲义、论文、技术文档与笔记的学习问答。"""
        result = answer_question(question, settings)
        answer = result.get("answer", "")
        context_docs = result.get("context", [])
        source_lines = build_source_labels(context_docs)
        sources = "\n".join(f"- {line}" for line in source_lines) if source_lines else "- 无"
        return f"回答：\n{answer}\n\n引用来源：\n{sources}"

    @tool
    def inspect_local_kb() -> str:
        """查看本地学习资料库是否已有文档，以及是否已经构建向量库。"""
        files = list_supported_files()
        payload = {
            "document_count": len(files),
            "vectorstore_ready": vectorstore_exists(),
            "files": files,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @tool
    def preview_retrieved_chunks(query: str, top_k: int = 4) -> str:
        """执行学习资料检索并返回片段预览，用于检查召回内容是否适合当前学习问题。"""
        docs = retrieve_documents(query, settings, k=top_k)
        preview = build_context_preview(docs)
        return json.dumps(preview, ensure_ascii=False, indent=2)

    @tool
    def export_agent_notes(filename: str, content: str) -> str:
        """把学习总结、研究笔记或复习提纲导出为 Markdown 文件。"""
        safe_name = filename if filename.endswith(".md") else f"{filename}.md"
        output_path = save_markdown(safe_name, content)
        return f"已导出到 {output_path}"

    @tool
    def web_search(query: str, max_results: int = 5) -> str:
        """联网搜索公开网页内容，适合补充学习资料中缺失的背景知识或时效性信息。"""
        try:
            results = search_web(query, max_results=max_results)
            return format_web_results(results)
        except Exception as exc:
            return f"联网搜索当前不可用：{exc}"

    return [rag_answer, inspect_local_kb, preview_retrieved_chunks, export_agent_notes, web_search]


async def _load_mcp_tools() -> list[Any]:
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


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content)


def _extract_agent_result(result: dict[str, Any]) -> tuple[str, list[str]]:
    messages = result.get("messages", [])
    final_answer = ""
    traces: list[str] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for call in getattr(message, "tool_calls", []) or []:
                name = call.get("name", "unknown_tool")
                args = call.get("args", {})
                traces.append(f"调用工具: {name} | 参数: {json.dumps(args, ensure_ascii=False)}")

            content = _stringify_content(message.content).strip()
            if content:
                final_answer = content

        if isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", "tool")
            snippet = _stringify_content(message.content).strip()
            if len(snippet) > 200:
                snippet = f"{snippet[:200]}..."
            traces.append(f"工具结果: {tool_name} | {snippet}")

    return final_answer, traces


async def _run_agent_async(user_input: str, settings: Settings) -> dict[str, Any]:
    mcp_tools = await _load_mcp_tools()
    agent = create_agent(
        model=get_chat_model(settings),
        tools=[*build_agent(settings), *mcp_tools],
        system_prompt=AGENT_SYSTEM_PROMPT,
    )
    result = await agent.ainvoke({"messages": [{"role": "user", "content": user_input}]})
    answer, traces = _extract_agent_result(result)
    return {"answer": answer, "traces": traces, "raw": result}


def run_agent(user_input: str, settings: Settings) -> dict[str, Any]:
    return asyncio.run(_run_agent_async(user_input, settings))
