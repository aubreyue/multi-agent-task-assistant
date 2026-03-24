from runtime.schemas import CheckerResult, RoundSummary, RuntimeResult


def test_runtime_result_shape():
    result = RuntimeResult(
        task_id=1,
        task="test",
        master_summary="summary",
        plans=[],
        worker_results=[],
        checker=CheckerResult(passed=False, score=0),
        final_answer="",
        traces=[],
        output_path=None,
    )
    assert result.task_id == 1


def test_round_summary_supports_gap_fields():
    summary = RoundSummary(
        round_index=1,
        master_summary="summary",
        worker_count=2,
        checker_passed=False,
        checker_score=72,
        completion_status="needs_revision",
        blocking_requirements=["作者信息缺失"],
        advisory_gaps=["可以补充更多引用"],
        stopping_reason="continue_revision",
    )
    assert summary.completion_status == "needs_revision"
    assert summary.blocking_requirements == ["作者信息缺失"]
    assert summary.advisory_gaps == ["可以补充更多引用"]
