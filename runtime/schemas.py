from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    return value


@dataclass
class WorkerTask:
    task_id: str
    instruction: str
    expected_output: str


@dataclass
class MasterPlan:
    goal: str
    subtasks: list[WorkerTask]
    stop_criteria: list[str]
    round_index: int


@dataclass
class WorkerResult:
    task_id: str
    summary: str
    artifacts: list[str] = field(default_factory=list)
    tool_traces: list[str] = field(default_factory=list)
    status: str = "success"


@dataclass
class CheckerResult:
    passed: bool
    score: int
    issues: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    blocking_requirements: list[str] = field(default_factory=list)
    advisory_gaps: list[str] = field(default_factory=list)
    suggested_action: str = "accept"
    completion_status: str = "accepted"
    notes: str = ""


@dataclass
class RoundSummary:
    round_index: int
    master_summary: str
    worker_count: int
    completed_tasks: list[str] = field(default_factory=list)
    checker_passed: bool = False
    checker_score: int = 0
    completion_status: str = "accepted"
    blocking_requirements: list[str] = field(default_factory=list)
    advisory_gaps: list[str] = field(default_factory=list)
    stopping_reason: str = ""
    compression_applied: bool = False


@dataclass
class RuntimeDiagnostics:
    total_rounds: int
    total_workers: int
    total_traces: int
    memory_hit_count: int
    memory_write_count: int
    compression_count: int


@dataclass
class MemoryRecord:
    memory_id: int | None
    memory_type: str
    title: str
    summary: str
    content: str
    source: str
    fingerprint: str
    quality_score: int
    created_at: str


@dataclass
class MemorySearchResult:
    memory_id: int
    summary: str
    score: float
    memory_type: str
    source: str


@dataclass
class ShortTermSnapshot:
    task_id: int
    pinned_context: list[str]
    recent_events: list[str]
    compressed_history: str
    token_estimate: int
    compression_applied: bool = False


@dataclass
class RuntimeResult:
    task_id: int
    task: str
    master_summary: str
    plans: list[MasterPlan]
    worker_results: list[WorkerResult]
    checker: CheckerResult
    final_answer: str
    traces: list[str]
    output_path: str | None
    memory_hits: list[MemorySearchResult] = field(default_factory=list)
    memory_writes: list[MemoryRecord] = field(default_factory=list)
    context_snapshots: list[ShortTermSnapshot] = field(default_factory=list)
    round_summaries: list[RoundSummary] = field(default_factory=list)
    diagnostics: RuntimeDiagnostics | None = None

    def to_dict(self) -> dict[str, Any]:
        return serialize(self)
