import json

import pytest

from core.ai_core import generation_job_repository as repository_module
from core.ai_core.generation_job_repository import (
    GenerationJobPersistenceError,
    GenerationJobReceiptError,
    GenerationJobRepository,
)
from core.ai_core.generation_queue import GenerationQueue, GenerationTask
from core.ai_core.providers.video.remote_video_provider import RemoteVideoProvider


RECEIPT_KEYS = {
    "format_version",
    "task_id",
    "task_type",
    "status",
    "job_id",
    "provider",
    "metadata",
    "submitted_at",
}


def submitted_task(tmp_path, name="deterministic-remote-video"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    provider = RemoteVideoProvider(name=name)
    task = GenerationTask(
        task_type="video",
        prompt="Generate a deterministic submitted job",
        provider=provider,
        project_path=tmp_path,
        metadata={"scene_id": 1, "shot_id": 2, "private": "excluded"},
    )
    queue = GenerationQueue()
    queue.add_task(task)

    return provider, task, queue


def assert_no_ready_asset(project_path, task):
    assert task.output is None
    assert not (project_path / "assets" / "registry.json").exists()
    assert list(project_path.rglob("asset.json")) == []
    assert not (project_path / "assets" / "versions").exists()


def test_submitted_receipt_preserves_minimal_identity_without_ready_asset(
    tmp_path,
):
    provider, task, queue = submitted_task(tmp_path)

    processed_task = queue.process_next()

    assert processed_task is task
    assert processed_task.status == "submitted"
    assert isinstance(queue.job_repository, GenerationJobRepository)

    receipt_path = queue.job_repository.receipt_path(task.task_id)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert set(receipt) == RECEIPT_KEYS
    assert receipt["format_version"] == 1
    assert receipt["task_id"] == task.task_id
    assert receipt["task_type"] == task.task_type
    assert receipt["status"] == "submitted"
    assert receipt["job_id"] == task.result["job_id"]
    assert receipt["provider"] == provider.name
    assert receipt["metadata"] == {"scene_id": 1, "shot_id": 2}
    assert isinstance(receipt["submitted_at"], str)
    assert receipt["submitted_at"]
    assert list(receipt_path.parent.glob("*.json")) == [receipt_path]
    assert_no_ready_asset(tmp_path, task)


def test_fresh_repository_recovers_submitted_receipt_after_restart(tmp_path):
    _, task, queue = submitted_task(tmp_path)
    queue.process_next()

    expected_receipt = queue.job_repository.resume(task.task_id)
    fresh_repository = GenerationJobRepository(tmp_path)

    assert fresh_repository is not queue.job_repository
    assert fresh_repository.resume(task.task_id) == expected_receipt


def test_corrupt_or_invalid_receipt_fails_explicitly_without_rewrite(tmp_path):
    repository = GenerationJobRepository(tmp_path)
    receipt_path = repository.receipt_path("corrupt-task")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    corrupt_content = "{not-json"
    receipt_path.write_text(corrupt_content, encoding="utf-8")

    with pytest.raises(GenerationJobReceiptError, match="Corrupt"):
        repository.resume("corrupt-task")

    assert receipt_path.read_text(encoding="utf-8") == corrupt_content

    invalid_content = json.dumps(
        {
            "format_version": 1,
            "task_id": "corrupt-task",
            "status": "submitted",
        }
    )
    receipt_path.write_text(invalid_content, encoding="utf-8")

    with pytest.raises(GenerationJobReceiptError, match="fields"):
        repository.resume("corrupt-task")

    assert receipt_path.read_text(encoding="utf-8") == invalid_content


def test_atomic_replace_failure_preserves_previous_valid_receipt(
    tmp_path,
    monkeypatch,
):
    provider, task, _ = submitted_task(tmp_path)
    repository = GenerationJobRepository(tmp_path)
    original_result = provider.generate(task.prompt, quality=task.quality)
    original_receipt = repository.persist(task, original_result)
    receipt_path = repository.receipt_path(task.task_id)
    original_content = receipt_path.read_text(encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("deterministic replace failure")

    monkeypatch.setattr(repository_module.os, "replace", fail_replace)
    replacement_result = dict(original_result, job_id="replacement-job")

    with pytest.raises(GenerationJobPersistenceError, match="Cannot persist"):
        repository.persist(task, replacement_result)

    assert receipt_path.read_text(encoding="utf-8") == original_content
    assert json.loads(original_content) == original_receipt
    assert list(receipt_path.parent.glob("*.tmp")) == []


def test_post_submit_observability_failure_preserves_durable_job_without_asset(
    tmp_path,
):
    class FailingAudit:
        def record(self, event, data):
            if event == "generation_submitted":
                raise OSError("deterministic audit failure")

    class FailingEvents:
        def emit(self, event, data):
            if event == "generation_submitted":
                raise OSError("deterministic event failure")

    for observer in ("audit", "events"):
        project_path = tmp_path / observer
        provider, task, _ = submitted_task(project_path, name=f"{observer}-video")
        repository = GenerationJobRepository(project_path)
        queue = GenerationQueue(job_repository=repository)
        queue.add_task(task)

        if observer == "audit":
            queue._audit = lambda current_task: FailingAudit()
        else:
            queue._events = lambda current_task: FailingEvents()

        processed_task = queue.process_next()
        recovered = GenerationJobRepository(project_path).resume(task.task_id)

        assert processed_task is task
        assert processed_task.status == "submitted"
        assert processed_task.result["status"] == "submitted"
        assert recovered["job_id"] == processed_task.result["job_id"]
        assert recovered["provider"] == provider.name
        assert_no_ready_asset(project_path, processed_task)
