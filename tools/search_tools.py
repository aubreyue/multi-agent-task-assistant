from __future__ import annotations

from langchain_core.tools import tool

from web_tools import format_web_results, search_web


def build_search_tools():
    @tool
    def web_search(query: str, max_results: int = 5) -> str:
        """联网搜索公开网页内容，适合补充本地资料中没有的信息。"""
        try:
            return format_web_results(search_web(query, max_results=max_results))
        except Exception as exc:
            return f"联网搜索当前不可用：{exc}"

    return [web_search]
