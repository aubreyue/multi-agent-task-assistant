from memory.short_term import ShortTermMemoryManager
from utils import Settings


def test_short_term_snapshot_contains_recent_events():
    manager = ShortTermMemoryManager(Settings("", "", "gpt-4o-mini", "text-embedding-3-small"))
    task_id = 9991
    manager.append_short_term_event(task_id, "user", "user_task", "测试任务")
    manager.append_short_term_event(task_id, "worker", "worker_result", "执行结果")
    snapshot = manager.get_context_snapshot(task_id)
    assert snapshot.task_id == task_id
    assert snapshot.pinned_context
