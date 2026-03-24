from __future__ import annotations

import json
from textwrap import dedent

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from qa_chain import get_chat_model
from runtime.schemas import CheckerResult, WorkerResult
from utils import Settings


CHECKER_PROMPT = PromptTemplate.from_template(
    dedent(
        """
        你是 Final Checker。请根据用户任务、stop criteria、worker 结果和最终候选答案，输出 JSON：
        {{
          "passed": true,
          "score": 0,
          "issues": [],
          "missing_requirements": [],
          "blocking_requirements": [],
          "advisory_gaps": [],
          "suggested_action": "accept 或 revise",
          "completion_status": "accepted / accepted_with_gaps / needs_revision",
          "notes": "简要审核意见"
        }}

        审核重点：
        1. 是否完成用户任务
        2. 是否有足够证据支持
        3. 本地资料不足时是否进行了补充搜索

        用户任务：
        {task}

        stop criteria:
        {criteria}

        worker 结果：
        {worker_results}

        候选最终答案：
        {final_answer}
        """
    )
)


def run_checker(task: str, criteria: list[str], worker_results: list[WorkerResult], final_answer: str, settings: Settings) -> CheckerResult:
    model = get_chat_model(settings)
    serialized_results = "\n\n".join(f"{item.task_id}: {item.summary[:360]}" for item in worker_results[:4])
    condensed_final_answer = final_answer[:1500]
    chain = CHECKER_PROMPT | model | StrOutputParser()
    raw = chain.invoke(
        {
            "task": task,
            "criteria": "\n".join(f"- {item}" for item in criteria),
            "worker_results": serialized_results or "无",
            "final_answer": condensed_final_answer,
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
            "passed": bool(final_answer.strip()),
            "score": 80 if final_answer.strip() else 20,
            "issues": [] if final_answer.strip() else ["未生成有效结果"],
            "missing_requirements": [] if final_answer.strip() else ["需要输出最终答案"],
            "blocking_requirements": [] if final_answer.strip() else ["需要输出最终答案"],
            "advisory_gaps": [],
            "suggested_action": "accept" if final_answer.strip() else "revise",
            "completion_status": "accepted" if final_answer.strip() else "needs_revision",
            "notes": cleaned_raw or "已完成基础审核。",
        }
    passed = bool(payload.get("passed", False))
    score_raw = payload.get("score", 85 if passed else 40)
    try:
        score = int(score_raw)
    except (TypeError, ValueError):
        score = 85 if passed else 40
    issues = payload.get("issues") or []
    missing_requirements = payload.get("missing_requirements") or []
    blocking_requirements = payload.get("blocking_requirements") or []
    advisory_gaps = payload.get("advisory_gaps") or []
    suggested_action = payload.get("suggested_action", "accept")
    completion_status = payload.get("completion_status", "accepted" if passed else "needs_revision")
    notes = payload.get("notes", "")

    if not blocking_requirements and missing_requirements:
        if suggested_action == "revise" or not passed:
            blocking_requirements = missing_requirements
        else:
            advisory_gaps = [*advisory_gaps, *missing_requirements]

    if blocking_requirements:
        passed = False
        suggested_action = "revise"
        completion_status = "needs_revision"
        if score >= 85:
            score = 75
    elif advisory_gaps:
        if passed:
            suggested_action = "accept"
            completion_status = "accepted_with_gaps"

    if score < 60:
        passed = False
        suggested_action = "revise"
        completion_status = "needs_revision"

    if passed:
        suggested_action = "accept"
        if completion_status == "needs_revision":
            completion_status = "accepted"

    return CheckerResult(
        passed=passed,
        score=score,
        issues=issues,
        missing_requirements=missing_requirements,
        blocking_requirements=blocking_requirements,
        advisory_gaps=advisory_gaps,
        suggested_action=suggested_action,
        completion_status=completion_status,
        notes=notes,
    )
