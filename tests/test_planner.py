from runtime.planner import _build_gap_focused_subtasks


def test_gap_focused_subtasks_prioritize_source_related_gaps():
    tasks = _build_gap_focused_subtasks(
        "检查示例资料来源",
        round_index=2,
        revision_feedback="待补充缺口：\n- 作者或发布者信息\n- 证据支持不足",
    )
    instructions = [item.instruction for item in tasks]
    assert any("作者" in item or "发布者" in item or "来源" in item for item in instructions)
    assert any("证据" in item or "引用" in item for item in instructions)


def test_gap_focused_subtasks_empty_feedback_returns_empty_list():
    assert _build_gap_focused_subtasks("test", round_index=1, revision_feedback="") == []
