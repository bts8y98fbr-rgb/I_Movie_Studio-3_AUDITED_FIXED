import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.ai_core.generation_job_repository import (
    GenerationJobPersistenceError,
    GenerationJobRepository,
)
from core.ai_core.generation_queue import GenerationTask


RESULT_LIFECYCLE_MODULE = (
    "core.ai_core.generation_job_result_lifecycle"
)


class ResultProvider:
    def __init__(
        self,
        name="deterministic-remote-video",
        response=None,
        error=None,
    ):
        self.name = name
        self.response = response
        self.error = error
        self.calls = []

    def get_result(self, job_id):
        self.calls.append(job_id)

        if self.error is not None:
            raise self.error

        return self.response


class ProviderResolver:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def get(self, name):
        self.calls.append(name)
        return self.provider


class RetrievedWriteFailRepository(
    GenerationJobRepository
):
    def _atomic_write(self, target, record):
        target = Path(target)

        if target.parent.name == "retrieved":
            raise GenerationJobPersistenceError(
                "deterministic retrieved write failure"
            )

        return super()._atomic_write(
            target,
            record,
        )


class FailingAudit:
    def record(self, event, data):
        raise OSError(
            "deterministic retrieval audit failure"
        )


class FailingEvents:
    def emit(self, event, data):
        raise OSError(
            "deterministic retrieval event failure"
        )


def lifecycle_contract():
    try:
        module = importlib.import_module(
            RESULT_LIFECYCLE_MODULE
        )
    except ModuleNotFoundError as exc:
        if exc.name != RESULT_LIFECYCLE_MODULE:
            raise

        pytest.fail(
            "Stage 2J result retrieval lifecycle is missing: "
            "expected "
            "core.ai_core.generation_job_result_lifecycle "
            "with "
            "GenerationJobResultLifecycle.retrieve_once(task_id)",
            pytrace=False,
        )

    lifecycle_type = getattr(
        module,
        "GenerationJobResultLifecycle",
        None,
    )
    lifecycle_error = getattr(
        module,
        "GenerationJobResultLifecycleError",
        None,
    )

    if (
        lifecycle_type is None
        or lifecycle_error is None
    ):
        pytest.fail(
            "Stage 2J result retrieval lifecycle contract "
            "is incomplete",
            pytrace=False,
        )

    return lifecycle_type, lifecycle_error


def build_lifecycle(
    repository,
    resolver,
    audit=None,
    events=None,
):
    lifecycle_type, lifecycle_error = (
        lifecycle_contract()
    )

    lifecycle = lifecycle_type(
        job_repository=repository,
        provider_resolver=resolver,
        audit=audit,
        events=events,
    )

    assert callable(
        getattr(lifecycle, "retrieve_once", None)
    ), (
        "Stage 2J lifecycle must expose "
        "retrieve_once(task_id)"
    )

    return lifecycle, lifecycle_error


def create_submitted_receipt(
    project_path,
    repository_type=GenerationJobRepository,
    provider_name="deterministic-remote-video",
    job_id="job-001",
):
    repository = repository_type(project_path)

    task = GenerationTask(
        task_type="video",
        prompt="Retrieve one durable remote result",
        provider=SimpleNamespace(
            name=provider_name
        ),
        project_path=project_path,
        metadata={
            "scene_id": 1,
            "shot_id": 2,
        },
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

    receipt_path = repository.receipt_path(
        task.task_id
    )

    return (
        repository,
        task,
        receipt_path,
        receipt_path.read_bytes(),
    )


def make_terminal_record(
    repository,
    task,
    status="succeeded",
    provider_name=None,
    job_id="job-001",
    task_type=None,
    metadata=None,
):
    provider_name = (
        provider_name
        or task.provider.name
    )

    record = {
        "format_version":
            repository.FORMAT_VERSION,
        "task_id":
            task.task_id,
        "task_type":
            task_type or task.task_type,
        "job_id":
            job_id,
        "provider":
            provider_name,
        "status":
            status,
        "metadata":
            dict(
                metadata
                if metadata is not None
                else {
                    "scene_id": 1,
                    "shot_id": 2,
                }
            ),
        "terminal_at":
            "2026-09-08T00:00:00+00:00",
    }

    if status == "succeeded":
        record.update(
            {
                "result_state":
                    "pending_retrieval",
                "asset_ready":
                    False,
            }
        )

    return record


def persist_terminal(
    repository,
    task,
    **overrides,
):
    record = make_terminal_record(
        repository,
        task,
        **overrides,
    )
    repository.persist_terminal(record)

    path = repository.terminal_path(
        task.task_id
    )

    return (
        path,
        path.read_bytes(),
        record,
    )


def create_job_with_terminal(
    project_path,
    terminal_status="succeeded",
    repository_type=GenerationJobRepository,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
    ) = create_submitted_receipt(
        project_path,
        repository_type=repository_type,
    )

    (
        terminal_path,
        terminal_before,
        terminal_record,
    ) = persist_terminal(
        repository,
        task,
        status=terminal_status,
    )

    return (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        terminal_record,
    )


def retrieved_path(project_path, task_id):
    return (
        Path(project_path)
        / "generation_jobs"
        / "retrieved"
        / f"{task_id}.json"
    )


def assert_source_records_unchanged(
    receipt_path,
    receipt_before,
    terminal_path,
    terminal_before,
):
    assert (
        receipt_path.read_bytes()
        == receipt_before
    )
    assert (
        terminal_path.read_bytes()
        == terminal_before
    )


def assert_no_ready_asset(project_path):
    project_path = Path(project_path)

    assert not (
        project_path
        / "assets"
        / "registry.json"
    ).exists()

    assert list(
        project_path.rglob("asset.json")
    ) == []

    assert not (
        project_path
        / "assets"
        / "versions"
    ).exists()


def valid_provider_result(
    provider_name="deterministic-remote-video",
    job_id="job-001",
):
    return {
        "job_id": job_id,
        "provider": provider_name,
        "artifact": "opaque-provider-result",
        "provider_status": "succeeded",
    }


def assert_retrieved_record(
    record,
    task,
    provider_result,
):
    assert record["format_version"] == 1
    assert record["task_id"] == task.task_id
    assert record["task_type"] == task.task_type
    assert record["job_id"] == "job-001"
    assert (
        record["provider"]
        == "deterministic-remote-video"
    )
    assert record["metadata"] == {
        "scene_id": 1,
        "shot_id": 2,
    }
    assert record["result_state"] == "retrieved"
    assert record["asset_ready"] is False
    assert (
        record["provider_result"]
        == provider_result
    )
    assert isinstance(
        record["retrieved_at"],
        str,
    )
    assert record["retrieved_at"]
    assert record.get("task_status") != "done"


def test_successful_pending_retrieval_is_durable_without_asset(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    provider_response = valid_provider_result()
    provider = ResultProvider(
        response=provider_response
    )
    resolver = ProviderResolver(provider)

    lifecycle, _ = build_lifecycle(
        repository,
        resolver,
    )

    outcome = lifecycle.retrieve_once(
        task.task_id
    )

    path = retrieved_path(
        tmp_path,
        task.task_id,
    )

    assert path.is_file()

    durable = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert outcome == durable

    expected_provider_result = dict(
        provider_response
    )

    assert_retrieved_record(
        durable,
        task,
        expected_provider_result,
    )

    assert resolver.calls == [
        provider.name
    ]
    assert provider.calls == [
        "job-001"
    ]

    provider.response["artifact"] = (
        "mutated-after-retrieval"
    )

    assert (
        outcome["provider_result"]["artifact"]
        == "opaque-provider-result"
    )

    reread = json.loads(
        path.read_text(encoding="utf-8")
    )
    assert (
        reread["provider_result"]["artifact"]
        == "opaque-provider-result"
    )

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_existing_retrieved_record_is_restart_idempotent(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    provider = ResultProvider(
        response=valid_provider_result()
    )
    resolver = ProviderResolver(provider)

    lifecycle, _ = build_lifecycle(
        repository,
        resolver,
    )

    first = lifecycle.retrieve_once(
        task.task_id
    )

    path = retrieved_path(
        tmp_path,
        task.task_id,
    )
    retrieved_before = path.read_bytes()

    restarted_provider = ResultProvider(
        response={
            "job_id": "job-001",
            "provider":
                "deterministic-remote-video",
            "artifact":
                "must-never-be-requested",
        }
    )
    restarted_resolver = ProviderResolver(
        restarted_provider
    )

    restarted_lifecycle, _ = build_lifecycle(
        repository,
        restarted_resolver,
    )

    second = restarted_lifecycle.retrieve_once(
        task.task_id
    )

    assert second == first
    assert resolver.calls == [
        provider.name
    ]
    assert provider.calls == [
        "job-001"
    ]
    assert restarted_resolver.calls == []
    assert restarted_provider.calls == []
    assert path.read_bytes() == retrieved_before

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_failed_or_cancelled_terminal_is_ineligible(
    tmp_path,
):
    for status in (
        "failed",
        "cancelled",
    ):
        project_path = tmp_path / status

        (
            repository,
            task,
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
            _,
        ) = create_job_with_terminal(
            project_path,
            terminal_status=status,
        )

        provider = ResultProvider(
            response=valid_provider_result()
        )
        resolver = ProviderResolver(provider)

        lifecycle, lifecycle_error = (
            build_lifecycle(
                repository,
                resolver,
            )
        )

        with pytest.raises(
            lifecycle_error,
            match=(
                "(?i)"
                "(terminal|succeed|eligible|retriev|"
                "failed|cancel)"
            ),
        ):
            lifecycle.retrieve_once(
                task.task_id
            )

        assert resolver.calls == []
        assert provider.calls == []
        assert not retrieved_path(
            project_path,
            task.task_id,
        ).exists()

        assert_source_records_unchanged(
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
        )
        assert_no_ready_asset(project_path)


def test_missing_terminal_fails_before_provider_resolution(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
    ) = create_submitted_receipt(tmp_path)

    provider = ResultProvider(
        response=valid_provider_result()
    )
    resolver = ProviderResolver(provider)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(terminal|succeed|retriev|missing)"
        ),
    ):
        lifecycle.retrieve_once(
            task.task_id
        )

    assert resolver.calls == []
    assert provider.calls == []
    assert receipt_path.read_bytes() == (
        receipt_before
    )
    assert not retrieved_path(
        tmp_path,
        task.task_id,
    ).exists()
    assert_no_ready_asset(tmp_path)


def test_submitted_terminal_identity_mismatch_fails_before_provider(
    tmp_path,
):
    cases = (
        (
            "task-type",
            {
                "task_type": "image",
            },
        ),
        (
            "provider",
            {
                "provider_name":
                    "different-provider",
            },
        ),
        (
            "job-id",
            {
                "job_id": "different-job",
            },
        ),
        (
            "metadata",
            {
                "metadata": {
                    "scene_id": 1,
                    "shot_id": 999,
                },
            },
        ),
    )

    for case_name, overrides in cases:
        project_path = (
            tmp_path / case_name
        )

        (
            repository,
            task,
            receipt_path,
            receipt_before,
        ) = create_submitted_receipt(
            project_path
        )

        (
            terminal_path,
            terminal_before,
            _,
        ) = persist_terminal(
            repository,
            task,
            status="succeeded",
            **overrides,
        )

        provider = ResultProvider(
            response=valid_provider_result()
        )
        resolver = ProviderResolver(provider)

        lifecycle, lifecycle_error = (
            build_lifecycle(
                repository,
                resolver,
            )
        )

        with pytest.raises(
            lifecycle_error,
            match=(
                "(?i)"
                "(identity|mismatch|metadata|"
                "provider|job|task)"
            ),
        ):
            lifecycle.retrieve_once(
                task.task_id
            )

        assert resolver.calls == []
        assert provider.calls == []
        assert not retrieved_path(
            project_path,
            task.task_id,
        ).exists()

        assert_source_records_unchanged(
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
        )
        assert_no_ready_asset(project_path)


def test_missing_provider_fails_without_retrieval(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    resolver = ProviderResolver(None)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(provider|unavailable|missing|not found)"
        ),
    ):
        lifecycle.retrieve_once(
            task.task_id
        )

    assert resolver.calls == [
        "deterministic-remote-video"
    ]
    assert not retrieved_path(
        tmp_path,
        task.task_id,
    ).exists()

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_resolved_provider_identity_mismatch_fails_before_get_result(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    provider = ResultProvider(
        name="different-provider",
        response=valid_provider_result(
            provider_name="different-provider"
        ),
    )
    resolver = ProviderResolver(provider)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)(provider|identity|mismatch)"
        ),
    ):
        lifecycle.retrieve_once(
            task.task_id
        )

    assert resolver.calls == [
        "deterministic-remote-video"
    ]
    assert provider.calls == []
    assert not retrieved_path(
        tmp_path,
        task.task_id,
    ).exists()

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_provider_without_callable_get_result_is_explicit_error(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    provider = SimpleNamespace(
        name="deterministic-remote-video"
    )
    resolver = ProviderResolver(provider)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)(get_result|result|retriev|provider)"
        ),
    ):
        lifecycle.retrieve_once(
            task.task_id
        )

    assert resolver.calls == [
        "deterministic-remote-video"
    ]
    assert not retrieved_path(
        tmp_path,
        task.task_id,
    ).exists()

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_non_mapping_or_empty_provider_result_is_rejected(
    tmp_path,
):
    responses = (
        None,
        [],
        {},
    )

    for index, response in enumerate(
        responses
    ):
        project_path = (
            tmp_path / f"shape-{index}"
        )

        (
            repository,
            task,
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
            _,
        ) = create_job_with_terminal(
            project_path
        )

        provider = ResultProvider(
            response=response
        )
        resolver = ProviderResolver(provider)

        lifecycle, lifecycle_error = (
            build_lifecycle(
                repository,
                resolver,
            )
        )

        with pytest.raises(
            lifecycle_error,
            match=(
                "(?i)"
                "(result|mapping|dictionary|empty|retriev)"
            ),
        ):
            lifecycle.retrieve_once(
                task.task_id
            )

        assert provider.calls == [
            "job-001"
        ]
        assert not retrieved_path(
            project_path,
            task.task_id,
        ).exists()

        assert_source_records_unchanged(
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
        )
        assert_no_ready_asset(project_path)


def test_provider_result_identity_mismatch_is_rejected(
    tmp_path,
):
    responses = (
        {
            "job_id": "different-job",
            "provider":
                "deterministic-remote-video",
            "artifact": "opaque",
        },
        {
            "job_id": "job-001",
            "provider": "different-provider",
            "artifact": "opaque",
        },
    )

    for index, response in enumerate(
        responses
    ):
        project_path = (
            tmp_path / f"identity-{index}"
        )

        (
            repository,
            task,
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
            _,
        ) = create_job_with_terminal(
            project_path
        )

        provider = ResultProvider(
            response=response
        )
        resolver = ProviderResolver(provider)

        lifecycle, lifecycle_error = (
            build_lifecycle(
                repository,
                resolver,
            )
        )

        with pytest.raises(
            lifecycle_error,
            match=(
                "(?i)"
                "(identity|mismatch|provider|job)"
            ),
        ):
            lifecycle.retrieve_once(
                task.task_id
            )

        assert provider.calls == [
            "job-001"
        ]
        assert not retrieved_path(
            project_path,
            task.task_id,
        ).exists()

        assert_source_records_unchanged(
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
        )
        assert_no_ready_asset(project_path)


def test_non_json_serializable_provider_result_is_rejected(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    response = valid_provider_result()
    response["not_json"] = {
        "set-value",
    }

    provider = ResultProvider(
        response=response
    )
    resolver = ProviderResolver(provider)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(json|serializ|result|retriev)"
        ),
    ):
        lifecycle.retrieve_once(
            task.task_id
        )

    assert provider.calls == [
        "job-001"
    ]
    assert not retrieved_path(
        tmp_path,
        task.task_id,
    ).exists()

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_sensitive_credentials_are_never_durably_persisted(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    response = valid_provider_result()
    response["credentials"] = {
        "api_key": "DO-NOT-PERSIST-STAGE-2J"
    }

    provider = ResultProvider(
        response=response
    )
    resolver = ProviderResolver(provider)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    outcome = None

    try:
        outcome = lifecycle.retrieve_once(
            task.task_id
        )
    except lifecycle_error:
        pass

    path = retrieved_path(
        tmp_path,
        task.task_id,
    )

    if path.exists():
        raw = path.read_text(
            encoding="utf-8"
        )

        assert (
            "DO-NOT-PERSIST-STAGE-2J"
            not in raw
        )

        if outcome is not None:
            serialized_outcome = json.dumps(
                outcome,
                ensure_ascii=False,
            )
            assert (
                "DO-NOT-PERSIST-STAGE-2J"
                not in serialized_outcome
            )
    else:
        assert outcome is None

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_malformed_existing_retrieval_fails_before_provider(
    tmp_path,
):
    malformed_records = (
        b"{not-json",
        (
            json.dumps(
                {
                    "format_version": 1,
                    "task_id": "task-001",
                }
            )
            + "\n"
        ).encode("utf-8"),
    )

    for index, malformed in enumerate(
        malformed_records
    ):
        project_path = (
            tmp_path / f"malformed-{index}"
        )

        (
            repository,
            task,
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
            _,
        ) = create_job_with_terminal(
            project_path
        )

        path = retrieved_path(
            project_path,
            task.task_id,
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_bytes(malformed)

        provider = ResultProvider(
            response=valid_provider_result()
        )
        resolver = ProviderResolver(provider)

        lifecycle, lifecycle_error = (
            build_lifecycle(
                repository,
                resolver,
            )
        )

        with pytest.raises(
            lifecycle_error,
            match=(
                "(?i)"
                "(retriev|record|corrupt|invalid|field)"
            ),
        ):
            lifecycle.retrieve_once(
                task.task_id
            )

        assert resolver.calls == []
        assert provider.calls == []
        assert path.read_bytes() == malformed

        assert_source_records_unchanged(
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
        )
        assert_no_ready_asset(project_path)


def test_provider_get_result_exception_is_wrapped_without_mutation(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(tmp_path)

    provider = ResultProvider(
        error=OSError(
            "deterministic provider retrieval failure"
        )
    )
    resolver = ProviderResolver(provider)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(retriev|result|provider|failure)"
        ),
    ):
        lifecycle.retrieve_once(
            task.task_id
        )

    assert resolver.calls == [
        provider.name
    ]
    assert provider.calls == [
        "job-001"
    ]
    assert not retrieved_path(
        tmp_path,
        task.task_id,
    ).exists()

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_durable_retrieval_write_failure_leaves_no_partial_record(
    tmp_path,
):
    (
        repository,
        task,
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
        _,
    ) = create_job_with_terminal(
        tmp_path,
        repository_type=(
            RetrievedWriteFailRepository
        ),
    )

    provider = ResultProvider(
        response=valid_provider_result()
    )
    resolver = ProviderResolver(provider)

    lifecycle, lifecycle_error = build_lifecycle(
        repository,
        resolver,
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(persist|write|retriev|durable|result)"
        ),
    ):
        lifecycle.retrieve_once(
            task.task_id
        )

    # One provider retrieval happened, but no
    # durable checkpoint exists. Stage 2J does
    # not hide the distributed repeat-risk with
    # an automatic retry or exactly-once claim.
    assert resolver.calls == [
        provider.name
    ]
    assert provider.calls == [
        "job-001"
    ]

    assert not retrieved_path(
        tmp_path,
        task.task_id,
    ).exists()

    assert_source_records_unchanged(
        receipt_path,
        receipt_before,
        terminal_path,
        terminal_before,
    )
    assert_no_ready_asset(tmp_path)


def test_observability_failure_cannot_destroy_durable_retrieval(
    tmp_path,
):
    for observer_name in (
        "audit",
        "events",
    ):
        project_path = (
            tmp_path / observer_name
        )

        (
            repository,
            task,
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
            _,
        ) = create_job_with_terminal(
            project_path
        )

        provider = ResultProvider(
            response=valid_provider_result()
        )
        resolver = ProviderResolver(provider)

        lifecycle, _ = build_lifecycle(
            repository,
            resolver,
            audit=(
                FailingAudit()
                if observer_name == "audit"
                else None
            ),
            events=(
                FailingEvents()
                if observer_name == "events"
                else None
            ),
        )

        first = lifecycle.retrieve_once(
            task.task_id
        )

        path = retrieved_path(
            project_path,
            task.task_id,
        )

        assert path.is_file()
        retrieved_before = path.read_bytes()

        second = lifecycle.retrieve_once(
            task.task_id
        )

        assert second == first
        assert resolver.calls == [
            provider.name
        ]
        assert provider.calls == [
            "job-001"
        ]
        assert (
            path.read_bytes()
            == retrieved_before
        )

        assert_source_records_unchanged(
            receipt_path,
            receipt_before,
            terminal_path,
            terminal_before,
        )
        assert_no_ready_asset(project_path)
