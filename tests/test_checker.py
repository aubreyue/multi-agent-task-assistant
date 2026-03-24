from runtime.schemas import WorkerResult
from runtime.checker import CheckerResult


def test_checker_result_dataclass():
    result = CheckerResult(passed=True, score=90)
    assert result.passed is True
    assert result.score == 90


def test_checker_result_supports_gap_classification():
    result = CheckerResult(
        passed=False,
        score=65,
        blocking_requirements=["作者信息缺失"],
        advisory_gaps=["可补充更多背景"],
        completion_status="needs_revision",
    )
    assert result.blocking_requirements == ["作者信息缺失"]
    assert result.advisory_gaps == ["可补充更多背景"]
    assert result.completion_status == "needs_revision"
