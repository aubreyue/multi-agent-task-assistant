from __future__ import annotations

import json
import os
from typing import Any

import certifi
import requests
import urllib3
from dotenv import load_dotenv
from requests.exceptions import SSLError


TAVILY_SEARCH_URL = "https://api.tavily.com/search"


load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _search_with_http(api_key: str, query: str, max_results: int) -> dict[str, Any]:
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "topic": "general",
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False,
    }
    try:
        response = requests.post(
            TAVILY_SEARCH_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20,
            verify=certifi.where(),
        )
        response.raise_for_status()
        return response.json()
    except SSLError:
        # Some local Python distributions intermittently fail to locate the CA
        # chain during runtime tool execution. Retry once with verify disabled
        # as a dev/demo fallback so the multi-agent loop can keep working.
        response = requests.post(
            TAVILY_SEARCH_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20,
            verify=False,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        detail = exc.response.text if exc.response is not None else str(exc)
        raise RuntimeError(f"Tavily HTTP 接口返回错误：{detail}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Tavily HTTP 请求失败：{exc}") from exc


def search_web(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search the public web and return lightweight result metadata."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 TAVILY_API_KEY，请先在 .env 中配置 Tavily 搜索密钥。")

    try:
        from tavily import TavilyClient
    except ImportError:
        TavilyClient = None

    if TavilyClient is not None:
        try:
            client = TavilyClient(api_key=api_key)
            response = client.search(
                query=query,
                max_results=max_results,
                topic="general",
                search_depth="advanced",
                include_answer=False,
                include_raw_content=False,
            )
        except Exception as exc:
            raise RuntimeError(f"联网搜索失败：{exc}") from exc
    else:
        response = _search_with_http(api_key, query, max_results)

    formatted: list[dict[str, Any]] = []
    for item in response.get("results", []):
        formatted.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
        )
    return formatted


def format_web_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "没有检索到可用网页结果。"

    lines: list[str] = []
    for idx, item in enumerate(results, start=1):
        title = item.get("title", "无标题")
        url = item.get("url", "")
        snippet = item.get("snippet", "")
        lines.append(f"{idx}. {title}")
        if url:
            lines.append(f"链接: {url}")
        if snippet:
            lines.append(f"摘要: {snippet}")
        lines.append("")
    return "\n".join(lines).strip()
