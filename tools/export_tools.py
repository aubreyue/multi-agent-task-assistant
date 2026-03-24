from __future__ import annotations

from langchain_core.tools import tool

from qa_chain import save_markdown


def build_export_tools():
    @tool
    def export_agent_notes(filename: str, content: str) -> str:
        """把运行结果、研究笔记或总结导出为 Markdown 文件。"""
        safe_name = filename if filename.endswith(".md") else f"{filename}.md"
        output_path = save_markdown(safe_name, content)
        return str(output_path)

    return [export_agent_notes]
