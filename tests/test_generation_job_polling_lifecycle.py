import importlib
import json
from types import SimpleNamespace

import pytest

from core.ai_core.generation_job_repository import GenerationJobRepository
from core.ai_core.generation_queue import GenerationTask


LIFECYCLE_MODULE = "core.ai_core.generation_job_lifecycle"


class StatusProvider:
    def __init__(self, name, response):
        self.name = name
        self.response = dict(response)
        self.calls = []

    def get_status(self, job_id):
        self.calls.append(job_id)
        return dict(self.response)


class ProviderResolver:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def get(self, name):
        self.calls.append(name)
        return self.provider


def lifecycle_contract():
    try:
        module = importlib.import_module(LIFECYCLE_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != LIFECYCLE_MODULE:
            raise

        pytest.fail(
            "Stage 2H lifecycle contract is missing: expected "
            "core.ai_core.generation_job_lifecycle with "
            "GenerationJobLifecycle.poll_once(task_id)",
            pytrace=False,
        )

    lifecycle_type = getattr(module, "GenerationJobLifecycle", None)
    lifecycle_error = getattr(module, "GenerationJobLifecycleError", None)

    if lifecycle_type is None or lifecycle_error is None:
        pytest.fail(
            "Stage 2H lifecycle contract is incomplete: expected "
            "GenerationJobLifecycle and GenerationJobLifecycleError",
            pytrace=False,
        )

    return lifecycle_type, lifecycle_error


def create_submitted_receipt(
    project_path,
    provider_name="deterministic-remote-video",
    job_id="job-001",
):
    project_path.mkdir(parents=True, exist_ok=True)
    repository = GenerationJobRepository(project_path)
    task = GenerationTask(
        task_type="video",
        prompt="Persist one submitted remote job",
        provider=SimpleNamespace(name=provider_name),
        project_path=project_path,
        metadata={"scene_id": 1, "shot_id": 2},
    )
    task.task_id = "task-001"
    repository.persist(
        task,
        {
            "status": "submitted",
            "job_id": job_id,
            "provider": provider_name,
        },
    )

    receipt_path = repository.receipt_path(task.task_id)

    return repository, task, receipt_path, receipt_path.read_bytes()


def build_lifecycle(repository, resolver, audit=None, events=None):
    lifecycle_type, lifecycle_error = lifecycle_contract()
    lifecycle = lifecycle_type(
        job_repository=repository,
        provider_resolver=resolver,
        audit=audit,
        events=events,
    )

    assert callable(getattr(lifecycle, "poll_once", None)), (
        "Stage 2H lifecycle service must expose poll_once(task_id)"
    )

    return lifecycle, lifecycle_error


def terminal_path(project_path, task_id):
    return (
        project_path
        / "generation_jobs"
        / "terminal"
        / f"{task_id}.json"
    )


def assert_no_ready_asset(project_path):
    assert not (project_path / "assets" / "registry.json").exists()
    assert list(project_path.rglob("asset.json")) == []
    assert not (project_path / "assets" / "versions").exists()


def assert_terminal_identity(record, task, provider_name, job_id, status):
    assert record["format_version"] == 1
    assert record["task_id"] == task.task_id
    assert record["task_type"] == task.task_type
    assert record["job_id"] == job_id
    assert record["provider"] == provider_name
    assert record["status"] == status
    assert record["metadata"] == {"scene_id": 1, "shot_id": 2}
    assert isinstance(record["terminal_at"], str)
    assert record["terminal_at"]


def test_processing_or_running_poll_is_nonterminal_and_nonmutating(tmp_path):
    for remote_status in ("processing", "running"):
        project_path = tmp_path / remote_status
        repository, task, receipt_path, receipt_before = (
            create_submitted_receipt(project_path)
        )
        provider = StatusProvider(
            name="deterministic-remote-video",
            response={
                "status": remote_status,
                "job_id": "job-001",
                "provider": "deterministic-remote-video",
            },
        )
        resolver = ProviderResolver(provider)
        lifecycle, _ = build_lifecycle(repository, resolver)

        current = lifecycle.poll_once(task.task_id)

        assert current["status"] == "running"
        assert current["job_id"] == "job-001"
        assert current["provider"] == provider.name
        assert resolver.calls == [provider.name]
        assert provider.calls == ["job-001"]
        assert receipt_path.read_bytes() == receipt_before
        assert not terminal_path(project_path, task.task_id).exists()
        assert_no_ready_asset(project_path)


def test_failed_or_cancelled_poll_persists_separate_terminal_record(tmp_path):
    for remote_status in ("failed", "cancelled"):
        project_path = tmp_path / remote_status
        repository, task, receipt_path, receipt_before = (
            create_submitted_receipt(project_path)
        )
        provider = StatusProvider(
            name="deterministic-remote-video",
            response={
                "status": remote_status,
                "job_id": "job-001",
                "provider": "deterministic-remote-video",
            },
        )
        lifecycle, _ = build_lifecycle(
            repository,
            ProviderResolver(provider),
        )

        outcome = lifecycle.poll_once(task.task_id)
        durable_path = terminal_path(project_path, task.task_id)
        durable_outcome = json.loads(durable_path.read_text(encoding="utf-8"))

        assert outcome == durable_outcome
        assert_terminal_identity(
            durable_outcome,
            task,
            provider.name,
            "job-001",
            remote_status,
        )
        assert receipt_path.read_bytes() == receipt_before
        assert_no_ready_asset(project_path)


def test_remote_success_stays_pending_retrieval_without_ready_asset(tmp_path):
    repository, task, receipt_path, receipt_before = create_submitted_receipt(
        tmp_path
    )
    provider = StatusProvider(
        name="deterministic-remote-video",
        response={
            "status": "succeeded",
            "job_id": "job-001",
            "provider": "deterministic-remote-video",
        },
    )
    lifecycle, _ = build_lifecycle(repository, ProviderResolver(provider))

    outcome = lifecycle.poll_once(task.task_id)
    durable_path = terminal_path(tmp_path, task.task_id)
    durable_outcome = json.loads(durable_path.read_text(encoding="utf-8"))

    assert outcome == durable_outcome
    assert_terminal_identity(
        durable_outcome,
        task,
        provider.name,
        "job-001",
        "succeeded",
    )
    assert durable_outcome["result_state"] == "pending_retrieval"
    assert durable_outcome["asset_ready"] is False
    assert durable_outcome.get("task_status") != "done"
    assert receipt_path.read_bytes() == receipt_before
    assert_no_ready_asset(tmp_path)


def test_terminal_poll_is_idempotent_before_provider_resolution(tmp_path):
    repository, task, receipt_path, receipt_before = create_submitted_receipt(
        tmp_path
    )
    provider = StatusProvider(
        name="deterministic-remote-video",
        response={
            "status": "failed",
            "job_id": "job-001",
            "provider": "deterministic-remote-video",
        },
    )
    resolver = ProviderResolver(provider)
    lifecycle, _ = build_lifecycle(repository, resolver)

    first_outcome = lifecycle.poll_once(task.task_id)
    durable_path = terminal_path(tmp_path, task.task_id)
    terminal_before = durable_path.read_bytes()
    restarted_provider = StatusProvider(
        name=provider.name,
        response={
            "status": "failed",
            "job_id": "job-001",
            "provider": provider.name,
        },
    )
    restarted_resolver = ProviderResolver(restarted_provider)
    restarted_lifecycle, _ = build_lifecycle(
        repository,
        restarted_resolver,
    )
    second_outcome = restarted_lifecycle.poll_once(task.task_id)

    assert second_outcome == first_outcome
    assert resolver.calls == [provider.name]
    assert provider.calls == ["job-001"]
    assert restarted_resolver.calls == []
    assert restarted_provider.calls == []
    assert durable_path.read_bytes() == terminal_before
    assert receipt_path.read_bytes() == receipt_before
    assert_no_ready_asset(tmp_path)


def test_missing_provider_fails_without_poll_or_durable_mutation(tmp_path):
    repository, task, receipt_path, receipt_before = create_submitted_receipt(
        tmp_path
    )
    resolver = ProviderResolver(None)
    lifecycle, lifecycle_error = build_lifecycle(repository, resolver)

    with pytest.raises(
        lifecycle_error,
        match="(?i)(provider|unavailable|missing|not found)",
    ):
        lifecycle.poll_once(task.task_id)

    assert resolver.calls == ["deterministic-remote-video"]
    assert receipt_path.read_bytes() == receipt_before
    assert not terminal_path(tmp_path, task.task_id).exists()
    assert_no_ready_asset(tmp_path)


def test_malformed_receipt_fails_before_provider_resolution(tmp_path):
    valid_receipt = {
        "format_version": 1,
        "task_id": "task-001",
        "task_type": "video",
        "status": "submitted",
        "job_id": "job-001",
        "provider": "deterministic-remote-video",
        "metadata": {"scene_id": 1, "shot_id": 2},
        "submitted_at": "2026-09-08T00:00:00+00:00",
    }
    malformed_receipts = [("invalid-json", b"{not-json")]

    for missing_field in ("provider", "job_id", "task_id"):
        receipt = dict(valid_receipt)
        del receipt[missing_field]
        malformed_receipts.append(
            (
                f"missing-{missing_field}",
                (json.dumps(receipt, indent=2) + "\n").encode("utf-8"),
            )
        )

    for case_name, receipt_before in malformed_receipts:
        project_path = tmp_path / case_name
        repository = GenerationJobRepository(project_path)
        receipt_path = repository.receipt_path("task-001")
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(receipt_before)
        resolver = ProviderResolver(None)
        lifecycle, lifecycle_error = build_lifecycle(repository, resolver)

        with pytest.raises(
            lifecycle_error,
            match="(?i)(receipt|corrupt|invalid|identity|field)",
        ):
            lifecycle.poll_once("task-001")

        assert resolver.calls == []
        assert receipt_path.read_bytes() == receipt_before
        assert not terminal_path(project_path, "task-001").exists()
        assert_no_ready_asset(project_path)


def test_provider_or_job_identity_mismatch_has_no_durable_mutation(tmp_path):
    cases = (
        (
            "resolver-provider",
            "different-provider",
            {
                "status": "failed",
                "job_id": "job-001",
                "provider": "different-provider",
            },
        ),
        (
            "response-provider",
            "deterministic-remote-video",
            {
                "status": "failed",
                "job_id": "job-001",
                "provider": "different-provider",
            },
        ),
        (
            "response-job",
            "deterministic-remote-video",
            {
                "status": "failed",
                "job_id": "different-job",
                "provider": "deterministic-remote-video",
            },
        ),
    )

    for case_name, resolved_name, response in cases:
        project_path = tmp_path / case_name
        repository, task, receipt_path, receipt_before = (
            create_submitted_receipt(project_path)
        )
        provider = StatusProvider(resolved_name, response)
        lifecycle, lifecycle_error = build_lifecycle(
            repository,
            ProviderResolver(provider),
        )

        with pytest.raises(
            lifecycle_error,
            match="(?i)(identity|provider|job|mismatch)",
        ):
            lifecycle.poll_once(task.task_id)

        assert receipt_path.read_bytes() == receipt_before
        assert not terminal_path(project_path, task.task_id).exists()
        assert_no_ready_asset(project_path)


def test_unknown_or_missing_provider_status_fails_without_terminal_record(
    tmp_path,
):
    responses = (
        {
            "job_id": "job-001",
            "provider": "deterministic-remote-video",
        },
        {
            "status": "unknown-provider-state",
            "job_id": "job-001",
            "provider": "deterministic-remote-video",
        },
        {
            "status": [],
            "job_id": "job-001",
            "provider": "deterministic-remote-video",
        },
    )

    for index, response in enumerate(responses):
        project_path = tmp_path / f"invalid-status-{index}"
        repository, task, receipt_path, receipt_before = (
            create_submitted_receipt(project_path)
        )
        provider = StatusProvider("deterministic-remote-video", response)
        lifecycle, lifecycle_error = build_lifecycle(
            repository,
            ProviderResolver(provider),
        )

        with pytest.raises(lifecycle_error, match="(?i)status"):
            lifecycle.poll_once(task.task_id)

        assert provider.calls == ["job-001"]
        assert receipt_path.read_bytes() == receipt_before
        assert not terminal_path(project_path, task.task_id).exists()
        assert_no_ready_asset(project_path)


def test_observability_failure_cannot_destroy_terminal_outcome(tmp_path):
    class FailingAudit:
        def record(self, event, data):
            raise OSError("deterministic terminal audit failure")

    class FailingEvents:
        def emit(self, event, data):
            raise OSError("deterministic terminal event failure")

    for observer_name in ("audit", "events"):
        project_path = tmp_path / observer_name
        repository, task, receipt_path, receipt_before = (
            create_submitted_receipt(project_path)
        )
        provider = StatusProvider(
            name="deterministic-remote-video",
            response={
                "status": "failed",
                "job_id": "job-001",
                "provider": "deterministic-remote-video",
            },
        )
        resolver = ProviderResolver(provider)
        lifecycle, _ = build_lifecycle(
            repository,
            resolver,
            audit=FailingAudit() if observer_name == "audit" else None,
            events=FailingEvents() if observer_name == "events" else None,
        )

        first_outcome = lifecycle.poll_once(task.task_id)
        durable_path = terminal_path(project_path, task.task_id)
        terminal_before = durable_path.read_bytes()
        second_outcome = lifecycle.poll_once(task.task_id)

        assert first_outcome == second_outcome
        assert provider.calls == ["job-001"]
        assert resolver.calls == [provider.name]
        assert durable_path.read_bytes() == terminal_before
        assert receipt_path.read_bytes() == receipt_before
        assert_no_ready_asset(project_path)
