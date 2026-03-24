from __future__ import annotations

import asyncio
import json
from pathlib import Path

from memory.long_term import LongTermMemoryManager
from memory.short_term import ShortTermMemoryManager
from runtime.checker import run_checker
from runtime.constants import DEFAULT_MAX_ROUNDS
from runtime.planner import build_plan
from runtime.schemas import MasterPlan, RoundSummary, RuntimeDiagnostics, RuntimeResult, WorkerResult, WorkerTask
from runtime.worker import run_worker
from storage.db import init_db
from storage.repositories import ArtifactRepository, MessageRepository, TaskRepository, WorkerRunRepository
from tools.registry import ToolRegistry
from utils import RUNS_DIR, Settings, ensure_directories


def _serialize_path(path: Path) -> str:
    return str(path.resolve())


def _build_final_answer(task: str, worker_results: list[WorkerResult], memory_hits: list) -> str:
    lines = [f"任务：{task}", "", "执行结果汇总："]
    for item in worker_results:
        lines.append(f"## {item.task_id}")
        lines.append(item.summary or "无结果")
        lines.append("")
    if memory_hits:
        lines.append("## 命中的长期记忆")
        for item in memory_hits:
            lines.append(f"- [{item.memory_type}] {item.summary}")
        lines.append("")
    return "\n".join(lines).strip()


def _needs_worker_retry(result: WorkerResult) -> bool:
    content = result.summary.strip()
    if result.status != "success":
        return True
    if len(content) < 24:
        return True
    weak_markers = ["未能生成有效结果", "无结果", "不知道", "无法判断"]
    return any(marker in content for marker in weak_markers)


def _build_research_note(worker_results: list[WorkerResult]) -> str:
    highlights: list[str] = []
    for item in worker_results[:3]:
        snippet = item.summary.strip()
        if snippet:
            highlights.append(f"- {snippet[:220]}")
    return "\n".join(highlights)


def _build_task_pattern(task: str, plans: list[MasterPlan]) -> str:
    if not plans:
        return ""
    latest_plan = plans[-1]
    subtask_lines = "\n".join(f"- {item.instruction}" for item in latest_plan.subtasks)
    return f"任务：{task}\n常见拆解方式：\n{subtask_lines}"


def _build_revision_feedback(checker) -> str:
    parts: list[str] = []
    if checker.blocking_requirements:
        parts.append("待补充缺口：")
        parts.extend(f"- {item}" for item in checker.blocking_requirements)
    if checker.issues:
        parts.append("已发现问题：")
        parts.extend(f"- {item}" for item in checker.issues)
    if checker.notes:
        parts.append(f"审核意见：{checker.notes}")
    return "\n".join(parts).strip()


def _determine_stopping_reason(checker, round_index: int, max_rounds: int) -> str:
    if checker.passed:
        return "checker_passed"
    if not checker.blocking_requirements:
        return "no_blocking_gaps"
    if round_index >= max_rounds:
        return "max_rounds_reached"
    if checker.suggested_action != "revise":
        return "checker_accept_without_revision"
    return "continue_revision"


async def _run_runtime_async(
    task: str,
    settings: Settings,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    criteria: list[str] | None = None,
) -> RuntimeResult:
    ensure_directories()
    init_db()

    task_repo = TaskRepository()
    message_repo = MessageRepository()
    worker_repo = WorkerRunRepository()
    artifact_repo = ArtifactRepository()
    task_id = task_repo.create_task(task)

    short_term = ShortTermMemoryManager(settings)
    long_term = LongTermMemoryManager(settings)
    registry = ToolRegistry(settings, short_term, task_id=task_id)
    tools = await registry.load_all_tools()

    plans: list[MasterPlan] = []
    all_worker_results: list[WorkerResult] = []
    traces: list[str] = []
    master_summary = ""
    round_summaries: list[RoundSummary] = []
    context_snapshots = []
    compression_count = 0
    memory_hits = []
    checker = run_checker(task, criteria or ["完成任务"], [], "", settings)
    revision_feedback = ""

    try:
        short_term.append_short_term_event(task_id, "user", "user_task", task)
        memory_hits = long_term.search(task)
        if memory_hits:
            short_term.append_short_term_event(
                task_id,
                "system",
                "memory_hits",
                "\n".join(f"[{item.memory_type}] {item.summary}" for item in memory_hits),
            )

        for round_index in range(1, max_rounds + 1):
            memory_context = "\n".join(f"[{item.memory_type}] {item.summary[:220]}" for item in memory_hits[:4])
            plan, master_summary = build_plan(
                task,
                memory_context,
                round_index,
                settings,
                user_criteria=criteria,
                revision_feedback=revision_feedback,
            )
            plans.append(plan)
            short_term.append_short_term_event(task_id, "master", "criteria", "\n".join(plan.stop_criteria))
            short_term.append_short_term_event(task_id, "master", "master_summary", master_summary)
            if revision_feedback:
                short_term.append_short_term_event(task_id, "master", "revision_feedback", revision_feedback)
            task_repo.update_task(task_id, current_round=round_index)

            round_results: list[WorkerResult] = []
            for worker_task in plan.subtasks:
                context = short_term.build_runtime_context(task_id, role="worker")
                result = await run_worker(worker_task, tools, context, settings)
                if _needs_worker_retry(result):
                    retry_task = WorkerResult(
                        task_id=result.task_id,
                        summary=f"Master 判定当前结果信息不足，已触发补救：{worker_task.instruction}",
                        tool_traces=[],
                        status="partial",
                    )
                    traces.append(f"{worker_task.task_id} | Master 触发补救重试")
                    short_term.append_short_term_event(task_id, "master", "worker_retry", retry_task.summary)
                    retry_context = short_term.build_runtime_context(task_id, role="worker_retry")
                    result = await run_worker(
                        WorkerTask(
                            task_id=worker_task.task_id,
                            instruction=f"补救执行并确保输出有信息量：{worker_task.instruction}",
                            expected_output=worker_task.expected_output,
                        ),
                        tools,
                        retry_context,
                        settings,
                    )
                round_results.append(result)
                all_worker_results.append(result)
                worker_repo.create_run(
                    task_id=task_id,
                    round_index=round_index,
                    worker_name=worker_task.task_id,
                    instruction=worker_task.instruction,
                    status=result.status,
                    summary=result.summary,
                    traces=result.tool_traces,
                )
                short_term.append_short_term_event(task_id, "worker", "worker_result", f"{worker_task.task_id}: {result.summary}")
                traces.extend([f"{worker_task.task_id} | {trace}" for trace in result.tool_traces])

            snapshot = short_term.compress_context_if_needed(task_id)
            context_snapshots.append(snapshot)
            if snapshot.compression_applied:
                traces.append("上下文管理: 已触发压缩")
                compression_count += 1

            final_answer = _build_final_answer(task, all_worker_results, memory_hits)
            checker = run_checker(task, plan.stop_criteria, all_worker_results, final_answer, settings)
            checker_feedback = checker.notes
            revision_feedback = _build_revision_feedback(checker)
            short_term.append_short_term_event(task_id, "checker", "checker_feedback", checker_feedback)
            traces.append(f"Checker: passed={checker.passed}, score={checker.score}, action={checker.suggested_action}")
            if revision_feedback:
                traces.append(f"Checker 缺口: {revision_feedback[:240]}")
            round_summaries.append(
                RoundSummary(
                    round_index=round_index,
                    master_summary=master_summary,
                    worker_count=len(round_results),
                    completed_tasks=[item.task_id for item in round_results],
                    checker_passed=checker.passed,
                    checker_score=checker.score,
                    completion_status=checker.completion_status,
                    blocking_requirements=checker.blocking_requirements,
                    advisory_gaps=checker.advisory_gaps,
                    stopping_reason=_determine_stopping_reason(checker, round_index, max_rounds),
                    compression_applied=snapshot.compression_applied,
                )
            )

            if round_summaries[-1].stopping_reason != "continue_revision":
                break
    except Exception as exc:
        task_repo.update_task(task_id, status="failed", final_answer=str(exc), checker_passed=0, checker_score=0)
        raise

    final_answer = _build_final_answer(task, all_worker_results, memory_hits)
    final_checker = checker if plans else run_checker(
        task,
        criteria or ["完成任务"],
        all_worker_results,
        final_answer,
        settings,
    )
    task_repo.update_task(
        task_id,
        status="completed" if final_checker.passed else "needs_review",
        final_answer=final_answer,
        checker_passed=1 if final_checker.passed else 0,
        checker_score=final_checker.score,
    )

    output = (
        f"# Multi-Agent 私人任务助理运行记录\n\n## 任务\n{task}\n\n## Master 总结\n{master_summary}\n\n## 最终输出\n{final_answer}\n"
        f"\n## Checker\n- passed: {final_checker.passed}\n- score: {final_checker.score}\n- notes: {final_checker.notes or '无'}\n"
    )
    if traces:
        output += "\n## 轨迹\n" + "\n".join(f"- {trace}" for trace in traces) + "\n"

    output_path = RUNS_DIR / f"runtime_task_{task_id}.md"
    output_path.write_text(output, encoding="utf-8")
    artifact_repo.add_artifact(task_id, "markdown", _serialize_path(output_path))

    memory_writes = long_term.maybe_store_high_value_result(
        task=task,
        final_answer=final_answer,
        checker=final_checker,
        source=f"task:{task_id}",
        task_pattern=_build_task_pattern(task, plans),
        research_note=_build_research_note(all_worker_results),
    )
    for item in memory_writes:
        traces.append(f"长期记忆写入: {item.title}")

    diagnostics = RuntimeDiagnostics(
        total_rounds=len(round_summaries),
        total_workers=len(all_worker_results),
        total_traces=len(traces),
        memory_hit_count=len(memory_hits),
        memory_write_count=len(memory_writes),
        compression_count=compression_count,
    )

    result = RuntimeResult(
        task_id=task_id,
        task=task,
        master_summary=master_summary,
        plans=plans,
        worker_results=all_worker_results,
        checker=final_checker,
        final_answer=final_answer,
        traces=traces,
        output_path=_serialize_path(output_path),
        memory_hits=memory_hits,
        memory_writes=memory_writes,
        context_snapshots=context_snapshots or [short_term.get_context_snapshot(task_id)],
        round_summaries=round_summaries,
        diagnostics=diagnostics,
    )
    return result


def run_multi_agent_runtime(
    task: str,
    settings: Settings,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    criteria: list[str] | None = None,
) -> dict:
    return asyncio.run(_run_runtime_async(task, settings, max_rounds=max_rounds, criteria=criteria)).to_dict()
