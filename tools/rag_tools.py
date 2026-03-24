from __future__ import annotations

import json

from langchain_core.tools import tool

from ingest import list_supported_files, vectorstore_exists
from qa_chain import answer_question, build_context_preview, build_source_labels, retrieve_documents
from utils import Settings


def build_rag_tools(settings: Settings):
    @tool
    def rag_answer(question: str) -> str:
        """基于本地资料检索并生成带来源的答案。"""
        try:
            result = answer_question(question, settings)
            answer = result.get("answer", "")
            context_docs = result.get("context", [])
            source_lines = build_source_labels(context_docs)
            sources = "\n".join(f"- {line}" for line in source_lines) if source_lines else "- 无"
            return f"回答：\n{answer}\n\n引用来源：\n{sources}"
        except Exception as exc:
            return f"本地资料问答当前不可用：{exc}"

    @tool
    def inspect_local_kb() -> str:
        """查看当前本地资料状态和索引是否已准备完成。"""
        payload = {
            "document_count": len(list_supported_files()),
            "vectorstore_ready": vectorstore_exists(),
            "files": list_supported_files(),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @tool
    def preview_retrieved_chunks(query: str, top_k: int = 4) -> str:
        """仅执行本地资料召回，返回片段预览。"""
        try:
            docs = retrieve_documents(query, settings, k=top_k)
            return json.dumps(build_context_preview(docs), ensure_ascii=False, indent=2)
        except Exception as exc:
            return json.dumps(
                {
                    "query": query,
                    "detail": f"本地资料召回当前不可用：{exc}",
                    "results": [],
                },
                ensure_ascii=False,
                indent=2,
            )

    return [rag_answer, inspect_local_kb, preview_retrieved_chunks]
