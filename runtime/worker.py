from __future__ import annotations

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage

from qa_chain import get_chat_model
from runtime.schemas import WorkerResult, WorkerTask
from utils import Settings


WORKER_SYSTEM_PROMPT = """
你是一个通用 Worker Subagent。
你会接收 Master 下发的单个子任务，并自主选择最合适的工具完成工作。

要求：
1. 优先使用工具，不要凭空回答。
2. 优先使用本地资料与长期记忆；信息不足时再联网。
3. 输出必须直接回应子任务，并包含有信息量的结果，不能只返回“无”或空白。
4. 如果资料不足，要明确说明不足点和已尝试过的方法。
5. 输出简洁、明确、可用于 Master 汇总。
"""


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


def _extract_result(result: dict[str, Any]) -> tuple[str, list[str]]:
    final_answer = ""
    traces: list[str] = []
    for message in result.get("messages", []):
        if isinstance(message, AIMessage):
            for call in getattr(message, "tool_calls", []) or []:
                traces.append(f"调用工具: {call.get('name', 'unknown_tool')} | 参数: {json.dumps(call.get('args', {}), ensure_ascii=False)}")
            content = _stringify_content(message.content).strip()
            if content:
                final_answer = content
        if isinstance(message, ToolMessage):
            snippet = _stringify_content(message.content).strip()
            if len(snippet) > 180:
                snippet = f"{snippet[:180]}..."
            traces.append(f"工具结果: {getattr(message, 'name', 'tool')} | {snippet}")
    return final_answer, traces


async def run_worker(task: WorkerTask, tools: list[Any], context: str, settings: Settings) -> WorkerResult:
    agent = create_agent(model=get_chat_model(settings), tools=tools, system_prompt=WORKER_SYSTEM_PROMPT)
    prompt = (
        f"运行上下文：\n{context}\n\n"
        f"子任务：{task.instruction}\n\n"
        f"期望输出：{task.expected_output}\n\n"
        "请给出可直接用于汇总的中文结果。如果信息不足，请说明不足点、已检查过的来源以及下一步建议。"
    )
    raw_result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
    summary, traces = _extract_result(raw_result)
    if not summary.strip() or len(summary.strip()) < 24:
        retry_prompt = (
            f"你刚才的结果过短或为空。请重新完成子任务，必须输出至少两句话，"
            f"并直接回答：{task.instruction}。如果确实无法完成，也要明确说明原因、已尝试的方法和资料限制。"
        )
        retry_result = await agent.ainvoke({"messages": [{"role": "user", "content": retry_prompt}]})
        retry_summary, retry_traces = _extract_result(retry_result)
        if retry_summary.strip():
            summary = retry_summary
            traces.extend([f"重试 | {trace}" for trace in retry_traces])
    status = "success" if summary.strip() else "partial"
    if not summary.strip():
        summary = f"未能生成有效结果。子任务：{task.instruction}。建议 Master 重新规划或补充资料。"
    return WorkerResult(task_id=task.task_id, summary=summary, tool_traces=traces, status=status)
