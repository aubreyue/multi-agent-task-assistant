from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ingest import build_vectorstore, list_supported_files, vectorstore_exists
from qa_chain import build_context_preview, retrieve_documents, summarize_knowledge_base
from utils import DATA_DIR, get_settings


mcp = FastMCP(
    name="knowledge-base-mcp",
    instructions=(
        "一个围绕本地资料库的 MCP server，提供资料列表、索引状态、检索和总结能力。"
    ),
)


@mcp.tool(description="查看当前资料库中的本地文件列表和基础信息。")
def list_knowledge_files() -> list[dict]:
    return list_supported_files(DATA_DIR)


@mcp.tool(description="查看索引和资料目录状态，用于 Agent 判断是否可以执行资料检索。")
def inspect_knowledge_base_status() -> dict:
    files = list_supported_files(DATA_DIR)
    return {
        "data_dir": str(DATA_DIR),
        "document_count": len(files),
        "vectorstore_ready": vectorstore_exists(),
        "files": files,
    }


@mcp.tool(description="重建资料向量索引。当新增讲义、论文或笔记后，可调用此工具刷新索引。")
def rebuild_knowledge_base() -> dict:
    settings = get_settings()
    try:
        chunk_count = build_vectorstore(settings)
        return {
            "status": "ok",
            "chunk_count": chunk_count,
            "message": f"资料索引重建完成，共写入 {chunk_count} 个文本块。",
        }
    except Exception as exc:
        return {"status": "error", "chunk_count": 0, "message": f"资料索引重建失败：{exc}"}


@mcp.tool(description="在本地资料库中执行语义检索，返回最相关的文本片段。")
def search_knowledge_base(query: str, top_k: int = 4) -> dict:
    settings = get_settings()
    try:
        docs = retrieve_documents(query, settings, k=top_k)
        return {
            "query": query,
            "result_count": len(docs),
            "results": build_context_preview(docs),
        }
    except Exception as exc:
        return {
            "query": query,
            "result_count": 0,
            "results": [],
            "detail": f"本地资料检索失败：{exc}",
        }


@mcp.tool(description="生成整个资料库的主题总结，适合快速了解当前内容。")
def summarize_knowledge_base_tool() -> dict:
    settings = get_settings()
    try:
        summary = summarize_knowledge_base(settings)
        return {"summary": summary}
    except Exception as exc:
        return {"summary": "", "detail": f"资料总结失败：{exc}"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
