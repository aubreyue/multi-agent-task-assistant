from runtime.schemas import WorkerTask


def test_worker_task_schema():
    task = WorkerTask(task_id="1", instruction="do work", expected_output="summary")
    assert task.task_id == "1"
