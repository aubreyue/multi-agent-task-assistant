from __future__ import annotations

import json
from textwrap import dedent

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from qa_chain import get_chat_model
from runtime.constants import DEFAULT_MAX_WORKERS_PER_ROUND
from runtime.schemas import MasterPlan, WorkerTask
from utils import Settings


PLAN_PROMPT = PromptTemplate.from_template(
    dedent(
        """
        你是 Master Agent。请根据用户任务、长期记忆命中和当前轮次，输出 JSON：
        {{
          "goal": "任务目标",
          "stop_criteria": ["..."],
          "subtasks": [
            {{"instruction": "...", "expected_output": "..."}}
          ],
          "master_summary": "本轮规划摘要"
        }}

        要求：
        1. 最多生成 {max_workers} 个子任务。
        2. 子任务要适合交给通用 worker 执行。
        3. 优先利用本地资料和历史记忆，不足时再联网。

        用户任务：
        {task}

        长期记忆命中：
        {memory_hits}

        上一轮待补充缺口：
        {revision_feedback}

        当前轮次：{round_index}
        """
    )
)


def _build_gap_focused_subtasks(task: str, round_index: int, revision_feedback: str) -> list[WorkerTask]:
    normalized_feedback = revision_feedback.strip()
    if not normalized_feedback:
        return []

    subtasks: list[WorkerTask] = []
    lower_feedback = normalized_feedback.lower()

    if any(keyword in normalized_feedback for keyword in ["作者", "发布者", "来源", "出处"]):
        subtasks.append(
            WorkerTask(
                task_id=f"round-{round_index}-worker-gap-local",
                instruction=f"优先检查本地资料与知识库片段中是否存在作者、发布者、出处或来源信息，并明确标注来自哪份资料：{task}",
                expected_output="来源核查结果与本地证据",
            )
        )
        subtasks.append(
            WorkerTask(
                task_id=f"round-{round_index}-worker-gap-web",
                instruction=f"如果本地资料仍缺作者、发布者或来源信息，则联网搜索并返回可引用的补充来源，同时说明搜索是否成功：{task}",
                expected_output="联网补充结果与外部来源",
            )
        )

    if any(keyword in normalized_feedback for keyword in ["证据", "依据", "支持", "引用"]):
        subtasks.append(
            WorkerTask(
                task_id=f"round-{round_index}-worker-gap-evidence",
                instruction=f"补充整理当前任务的关键证据、引用来源和依据片段，避免只给结论不说明依据：{task}",
                expected_output="证据清单与引用说明",
            )
        )

    if any(keyword in lower_feedback for keyword in ["总结", "摘要", "结构化", "提纲"]):
        subtasks.append(
            WorkerTask(
                task_id=f"round-{round_index}-worker-gap-structure",
                instruction=f"基于已有信息重写一版更完整的结构化结果，确保用户要求的摘要/提纲格式被满足：{task}",
                expected_output="结构化重写结果",
            )
        )

    deduped: list[WorkerTask] = []
    seen: set[str] = set()
    for item in subtasks:
        signature = " ".join(item.instruction.lower().split())
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(item)
        if len(deduped) >= DEFAULT_MAX_WORKERS_PER_ROUND:
            break
    return deduped


def build_plan(
    task: str,
    memory_hits: str,
    round_index: int,
    settings: Settings,
    user_criteria: list[str] | None = None,
    revision_feedback: str = "",
) -> tuple[MasterPlan, str]:
    model = get_chat_model(settings)
    chain = PLAN_PROMPT | model | StrOutputParser()
    memory_context = memory_hits[:1200] if memory_hits else "无"
    raw = chain.invoke(
        {
            "task": task,
            "memory_hits": memory_context,
            "revision_feedback": revision_feedback[:1000] if revision_feedback else "无",
            "round_index": round_index,
            "max_workers": DEFAULT_MAX_WORKERS_PER_ROUND,
        }
    )
    cleaned_raw = raw.strip()
    if cleaned_raw.startswith("```"):
        cleaned_raw = cleaned_raw.strip("`")
        cleaned_raw = cleaned_raw.replace("json\n", "", 1).strip()
    try:
        payload = json.loads(cleaned_raw)
    except json.JSONDecodeError:
        payload = {
            "goal": task,
            "stop_criteria": ["完成用户任务", "给出证据支持", "必要时联网补充"],
            "subtasks": [
                {
                    "instruction": f"围绕任务执行资料检索并整理核心信息：{task}"
                    + (f"；优先补齐这些缺口：{revision_feedback}" if revision_feedback else ""),
                    "expected_output": "结构化总结",
                },
            ],
            "master_summary": raw.strip() or f"围绕任务生成了第 {round_index} 轮执行计划。",
        }

    raw_subtasks = payload.get("subtasks", [])
    deduped_subtasks: list[dict] = []
    seen_signatures: set[str] = set()
    for item in raw_subtasks:
        instruction = str(item.get("instruction", "")).strip()
        expected_output = str(item.get("expected_output", "")).strip() or "结构化总结"
        if not instruction:
            continue
        signature = " ".join(instruction.lower().split())
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped_subtasks.append({"instruction": instruction, "expected_output": expected_output})
        if len(deduped_subtasks) >= DEFAULT_MAX_WORKERS_PER_ROUND:
            break

    subtasks = [
        WorkerTask(task_id=f"round-{round_index}-worker-{index}", instruction=item["instruction"], expected_output=item["expected_output"])
        for index, item in enumerate(deduped_subtasks, start=1)
    ]
    if not subtasks:
        subtasks = [
            WorkerTask(
                task_id=f"round-{round_index}-worker-1",
                instruction=f"围绕任务执行资料检索并整理核心信息：{task}",
                expected_output="结构化总结",
            )
        ]
    elif len(subtasks) == 1:
        subtasks.append(
            WorkerTask(
                task_id=f"round-{round_index}-worker-2",
                instruction=f"补充检查是否遗漏关键资料来源、限制条件或证据：{task}",
                expected_output="查漏补缺后的补充说明",
            )
        )
    if revision_feedback:
        deterministic_gap_tasks = _build_gap_focused_subtasks(task, round_index, revision_feedback)
        if deterministic_gap_tasks:
            existing_signatures = {" ".join(item.instruction.lower().split()) for item in subtasks}
            merged_subtasks = list(subtasks)
            for item in deterministic_gap_tasks:
                signature = " ".join(item.instruction.lower().split())
                if signature in existing_signatures:
                    continue
                merged_subtasks.append(item)
                existing_signatures.add(signature)
                if len(merged_subtasks) >= DEFAULT_MAX_WORKERS_PER_ROUND:
                    break
            subtasks = merged_subtasks[:DEFAULT_MAX_WORKERS_PER_ROUND]
    requested_criteria = [item.strip() for item in (user_criteria or []) if item and item.strip()]
    planned_criteria = payload.get("stop_criteria") or ["完成用户任务", "给出证据支持", "必要时联网补充"]
    merged_criteria: list[str] = []
    seen_criteria: set[str] = set()
    for item in [*requested_criteria, *planned_criteria]:
        normalized = str(item).strip()
        if not normalized:
            continue
        signature = " ".join(normalized.lower().split())
        if signature in seen_criteria:
            continue
        seen_criteria.add(signature)
        merged_criteria.append(normalized)

    plan = MasterPlan(
        goal=payload.get("goal", task),
        subtasks=subtasks,
        stop_criteria=merged_criteria or ["完成用户任务", "给出证据支持", "必要时联网补充"],
        round_index=round_index,
    )
    return plan, payload.get("master_summary", f"第 {round_index} 轮计划已生成。")
