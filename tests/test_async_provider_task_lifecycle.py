from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock

from core.ai_core.ai_audit_log import AIAuditLog
from core.ai_core.generation_queue import GenerationQueue, GenerationTask
from core.ai_core.providers.video.remote_video_provider import RemoteVideoProvider
from core.movie_engine.project_events import ProjectEvents


class SynchronousProvider:
    name = "deterministic-sync-video"

    def __init__(self):
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return {
            "asset_id": "sync-asset",
            "provider": self.name,
            "status": "success",
        }


def queued_task(provider, tmp_path):
    task = GenerationTask(
        task_type="video",
        prompt="Generate a deterministic video job",
        provider=provider,
        project_path=tmp_path,
        metadata={"scene_id": 1, "shot_id": 1},
    )
    queue = GenerationQueue()
    queue.add_task(task)
    return task, queue


def test_async_submission_preserves_state_job_and_provider_identity(tmp_path):
    provider = RemoteVideoProvider(name="deterministic-remote-video")
    provider_results = []
    provider_result_snapshots = []
    original_generate = provider.generate

    def capture_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        provider_results.append(result)
        provider_result_snapshots.append(deepcopy(result))
        return result

    provider.generate = capture_generate

    task, queue = queued_task(provider, tmp_path)

    processed_task = queue.process_next()

    assert processed_task is task
    assert len(provider_results) == 1
    assert isinstance(processed_task.result, dict)
    assert processed_task.result is provider_results[0]
    assert processed_task.result == provider_result_snapshots[0]
    assert processed_task.result["status"] == "submitted"
    assert isinstance(processed_task.result.get("job_id"), str)
    assert processed_task.result["job_id"]
    assert processed_task.result["job_id"] == provider_result_snapshots[0]["job_id"]
    assert processed_task.result["provider"] == provider.name
    assert provider.name == "deterministic-remote-video"
    assert processed_task.status == "submitted"


def test_async_submission_emits_submitted_without_completion(tmp_path):
    provider = RemoteVideoProvider(name="deterministic-remote-video")
    task, queue = queued_task(provider, tmp_path)

    assert queue.process_next() is task

    audit_events = [
        entry["event"]
        for entry in AIAuditLog(tmp_path).get_all()
    ]
    project_events = ProjectEvents(tmp_path)

    assert audit_events.count("generation_submitted") == 1
    assert len(project_events.find("generation_submitted")) == 1
    for completion in ("generation_complete", "generation_completed"):
        assert completion not in audit_events
        assert project_events.find(completion) == []


def test_async_submission_does_not_persist_ready_asset(tmp_path):
    provider = RemoteVideoProvider(name="deterministic-remote-video")
    task, queue = queued_task(provider, tmp_path)
    queue.save_result = Mock(wraps=queue.save_result)

    assert queue.process_next() is task

    queue.save_result.assert_not_called()
    assert not (tmp_path / "assets" / "registry.json").exists()
    assert list(tmp_path.rglob("asset.json")) == []
    assert not (tmp_path / "assets" / "versions").exists()
    assert not (tmp_path / "assets").exists()
    assert task.output is None


def test_sync_provider_preserves_legacy_completion_and_storage(tmp_path):
    provider = SynchronousProvider()
    task, queue = queued_task(provider, tmp_path)

    processed_task = queue.process_next()

    assert processed_task is task
    assert len(provider.calls) == 1
    assert processed_task.status == "done"
    assert processed_task.result["status"] == "success"

    audit_events = [
        entry["event"]
        for entry in AIAuditLog(tmp_path).get_all()
    ]
    project_events = ProjectEvents(tmp_path)

    assert audit_events.count("generation_complete") == 1
    assert "generation_submitted" not in audit_events
    assert len(project_events.find("generation_completed")) == 1
    assert project_events.find("generation_submitted") == []
    assert processed_task.output is not None
    assert Path(processed_task.output).exists()
    assert (tmp_path / "assets" / "registry.json").exists()
    asset = json.loads(Path(processed_task.output).read_text(encoding="utf-8"))
    assert asset["status"] == "done"
    assert asset["provider"] == provider.name
    assert asset["result"] == processed_task.result
    registry = json.loads(
        (tmp_path / "assets" / "registry.json").read_text(encoding="utf-8")
    )
    assert len(registry) == 1
    assert registry[0]["asset_id"] == "sync-asset"
    assert (
        tmp_path / "assets" / "versions" / "sync-asset" / "v001" / "asset.json"
    ).exists()
