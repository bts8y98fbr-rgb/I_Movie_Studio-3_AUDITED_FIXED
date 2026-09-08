import importlib
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.ai_core.generation_job_repository import (
    GenerationJobPersistenceError,
    GenerationJobRepository,
)
from core.ai_core.generation_job_result_lifecycle import (
    GenerationJobResultLifecycle,
)
from core.ai_core.generation_queue import (
    GenerationTask,
)
from core.ai_core.result_storage import (
    AIResultStorage,
)


ASSET_LIFECYCLE_MODULE = (
    "core.ai_core.generation_job_asset_lifecycle"
)

TASK_ID = "task-001"
JOB_ID = "job-001"
PROVIDER = "deterministic-remote-video"
TASK_TYPE = "video"
SCENE_ID = 1
SHOT_ID = 2


class FailingAudit:
    def record(self, event, data):
        raise OSError(
            "deterministic Stage 2K audit failure"
        )


class FailingEvents:
    def emit(self, event, data):
        raise OSError(
            "deterministic Stage 2K event failure"
        )


def lifecycle_contract():
    try:
        module = importlib.import_module(
            ASSET_LIFECYCLE_MODULE
        )
    except ModuleNotFoundError as exc:
        if exc.name != ASSET_LIFECYCLE_MODULE:
            raise

        pytest.fail(
            "Stage 2K asset finalization lifecycle is missing: "
            "expected "
            "core.ai_core.generation_job_asset_lifecycle "
            "with "
            "GenerationJobAssetLifecycle.finalize_once(task_id)",
            pytrace=False,
        )

    lifecycle_type = getattr(
        module,
        "GenerationJobAssetLifecycle",
        None,
    )
    lifecycle_error = getattr(
        module,
        "GenerationJobAssetLifecycleError",
        None,
    )

    if (
        lifecycle_type is None
        or lifecycle_error is None
    ):
        pytest.fail(
            "Stage 2K asset finalization lifecycle "
            "contract is incomplete",
            pytrace=False,
        )

    storage_method = getattr(
        AIResultStorage,
        "save_retrieved_result",
        None,
    )

    if not callable(storage_method):
        pytest.fail(
            "Stage 2K requires dedicated "
            "AIResultStorage.save_retrieved_result(...) "
            "and must not reconstruct a fake GenerationTask",
            pytrace=False,
        )

    return (
        module,
        lifecycle_type,
        lifecycle_error,
    )


def build_lifecycle(
    repository,
    audit=None,
    events=None,
):
    (
        module,
        lifecycle_type,
        lifecycle_error,
    ) = lifecycle_contract()

    lifecycle = lifecycle_type(
        job_repository=repository,
        audit=audit,
        events=events,
    )

    assert callable(
        getattr(
            lifecycle,
            "finalize_once",
            None,
        )
    ), (
        "Stage 2K lifecycle must expose "
        "finalize_once(task_id)"
    )

    return (
        module,
        lifecycle,
        lifecycle_error,
    )


def provider_result(
    asset_id_marker=False,
    asset_id=None,
):
    result = {
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "artifact": "opaque-remote-result",
        "provider_status": "succeeded",
    }

    if asset_id_marker:
        result["asset_id"] = asset_id

    return result


def create_source_chain(
    project_path,
    provider_payload=None,
    terminal_overrides=None,
    retrieved_overrides=None,
):
    project_path = Path(project_path)
    repository = GenerationJobRepository(
        project_path
    )

    task = GenerationTask(
        task_type=TASK_TYPE,
        prompt="Stage 2K durable finalization",
        provider=SimpleNamespace(
            name=PROVIDER
        ),
        quality="4k",
        project_path=project_path,
        metadata={
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
    )
    task.task_id = TASK_ID

    repository.persist(
        task,
        {
            "status": "submitted",
            "job_id": JOB_ID,
            "provider": PROVIDER,
        },
    )

    terminal = {
        "format_version":
            repository.FORMAT_VERSION,
        "task_id":
            TASK_ID,
        "task_type":
            TASK_TYPE,
        "job_id":
            JOB_ID,
        "provider":
            PROVIDER,
        "status":
            "succeeded",
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "terminal_at":
            "2026-09-08T00:00:00+00:00",
        "result_state":
            "pending_retrieval",
        "asset_ready":
            False,
    }

    if terminal_overrides:
        terminal.update(
            terminal_overrides
        )

    repository.persist_terminal(
        terminal
    )

    retrieved = {
        "format_version":
            repository.FORMAT_VERSION,
        "task_id":
            TASK_ID,
        "task_type":
            TASK_TYPE,
        "job_id":
            JOB_ID,
        "provider":
            PROVIDER,
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "result_state":
            "retrieved",
        "asset_ready":
            False,
        "provider_result":
            (
                provider_payload
                if provider_payload is not None
                else provider_result()
            ),
        "retrieved_at":
            "2026-09-08T00:01:00+00:00",
    }

    if retrieved_overrides:
        retrieved.update(
            retrieved_overrides
        )

    repository.persist_retrieved(
        retrieved
    )

    paths = {
        "submitted":
            repository.receipt_path(
                TASK_ID
            ),
        "terminal":
            repository.terminal_path(
                TASK_ID
            ),
        "retrieved":
            repository.retrieved_path(
                TASK_ID
            ),
    }

    source_bytes = {
        name: path.read_bytes()
        for name, path in paths.items()
    }

    return (
        repository,
        task,
        retrieved,
        paths,
        source_bytes,
    )


def make_task_snapshot(
    task_id=TASK_ID,
    task_type=TASK_TYPE,
    provider=PROVIDER,
    scene_id=SCENE_ID,
    shot_id=SHOT_ID,
):
    return {
        "task_id": task_id,
        "type": task_type,
        "status": "submitted",
        "metadata": {
            "scene_id": scene_id,
            "shot_id": shot_id,
            "timeline": {
                "duration": 4,
            },
            "shot_model_selection": {
                "selected_model": {
                    "name": "remote-model",
                },
            },
        },
        "result": {
            "status": "submitted",
            "job_id": JOB_ID,
            "provider": provider,
        },
        "provider": provider,
        "quality": "4k",
        "output": None,
    }


def make_shot(
    shot_id=SHOT_ID,
):
    return {
        "shot_id": shot_id,
        "director_prompt":
            "Stage 2K read-only render context",
        "timeline": {
            "start": 0,
            "duration": 4,
        },
        "camera": {
            "shot_type": "hero_reveal",
        },
        "shot_model_selection": {
            "selected_model": {
                "name": "remote-model",
            },
        },
    }


def write_generation_result(
    project_path,
    tasks=None,
):
    path = (
        Path(project_path)
        / "render_output"
        / f"scene_{SCENE_ID:03d}"
        / "generation_result.json"
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "scene_id": SCENE_ID,
        "created":
            "2026-09-08T00:00:00",
        "quality": "4k",
        "generated": 0,
        "failed": 0,
        "cancelled": 0,
        "submitted": 1,
        "running": 0,
        "pending": 1,
        "status": "pending",
        "tasks": (
            tasks
            if tasks is not None
            else [
                make_task_snapshot()
            ]
        ),
    }

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return path


def write_render_plan(
    project_path,
    shots=None,
):
    path = (
        Path(project_path)
        / "render"
        / f"scene_{SCENE_ID:03d}"
        / "render_plan.json"
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "scene_id": SCENE_ID,
        "render_settings": {
            "resolution": "3840x2160",
            "fps": 60,
            "hdr": True,
            "color_depth": 10,
        },
        "shots": (
            shots
            if shots is not None
            else [
                make_shot()
            ]
        ),
    }

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return path


def write_context(
    project_path,
    tasks=None,
    shots=None,
):
    generation_path = (
        write_generation_result(
            project_path,
            tasks=tasks,
        )
    )
    render_path = write_render_plan(
        project_path,
        shots=shots,
    )

    return {
        "generation":
            generation_path,
        "render":
            render_path,
        "generation_bytes":
            generation_path.read_bytes(),
        "render_bytes":
            render_path.read_bytes(),
    }


def prepare_full(
    project_path,
    provider_payload=None,
    terminal_overrides=None,
    retrieved_overrides=None,
    tasks=None,
    shots=None,
):
    chain = create_source_chain(
        project_path,
        provider_payload=provider_payload,
        terminal_overrides=terminal_overrides,
        retrieved_overrides=retrieved_overrides,
    )
    context = write_context(
        project_path,
        tasks=tasks,
        shots=shots,
    )

    return (*chain, context)


def finalized_path(
    project_path,
    task_id=TASK_ID,
):
    return (
        Path(project_path)
        / "generation_jobs"
        / "finalized"
        / f"{task_id}.json"
    )


def registry_path(project_path):
    return (
        Path(project_path)
        / "assets"
        / "registry.json"
    )


def canonical_asset_file(project_path):
    return (
        Path(project_path)
        / "assets"
        / TASK_TYPE
        / f"scene_{SCENE_ID:03d}"
        / f"shot_{SHOT_ID:03d}"
        / "asset.json"
    )


def version_file(
    project_path,
    asset_id,
    version=1,
):
    return (
        Path(project_path)
        / "assets"
        / "versions"
        / asset_id
        / f"v{version:03d}"
        / "asset.json"
    )


def generation_context(
    task_id=TASK_ID,
    job_id=JOB_ID,
):
    return {
        "task_id": task_id,
        "job_id": job_id,
        "source": "remote_retrieval",
    }


def make_registry_entry(
    asset_id,
    task_id=TASK_ID,
    job_id=JOB_ID,
    provider=PROVIDER,
    version=1,
):
    return {
        "asset_id": asset_id,
        "type": TASK_TYPE,
        "provider": provider,
        "model": {},
        "quality": "4k",
        "routing": {},
        "provider_capabilities": {},
        "generation_context":
            generation_context(
                task_id,
                job_id,
            ),
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "status": "generated",
        "version": version,
        "created":
            "2026-09-08T00:02:00",
    }


def write_registry(
    project_path,
    entries,
):
    path = registry_path(
        project_path
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            entries,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def read_registry(project_path):
    path = registry_path(
        project_path
    )
    if not path.exists():
        return []

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def write_version(
    project_path,
    entry,
):
    path = version_file(
        project_path,
        entry["asset_id"],
        entry["version"],
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            entry,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def make_asset_payload(
    asset_id,
    registry_entry=None,
    provider_payload=None,
):
    entry = (
        registry_entry
        if registry_entry is not None
        else make_registry_entry(
            asset_id
        )
    )

    return {
        "asset_id": asset_id,
        "type": TASK_TYPE,
        "prompt":
            "Stage 2K read-only render context",
        "provider": PROVIDER,
        "model": {},
        "quality": "4k",
        "status": "generated",
        "created":
            "2026-09-08T00:02:00",
        "registry": entry,
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "generation_context":
            generation_context(),
        "result": (
            provider_payload
            if provider_payload is not None
            else provider_result()
        ),
    }


def write_asset(
    project_path,
    asset_id,
    registry_entry=None,
    provider_payload=None,
):
    path = canonical_asset_file(
        project_path
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            make_asset_payload(
                asset_id,
                registry_entry,
                provider_payload,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_finalized_record(
    project_path,
    asset_id=TASK_ID,
    asset_file=None,
    registry_version=1,
    task_id=TASK_ID,
    job_id=JOB_ID,
    provider=PROVIDER,
):
    path = finalized_path(
        project_path,
        task_id,
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if asset_file is None:
        asset_file = canonical_asset_file(
            project_path
        )

    record = {
        "format_version": 1,
        "task_id": task_id,
        "task_type": TASK_TYPE,
        "job_id": job_id,
        "provider": provider,
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "result_state": "finalized",
        "asset_ready": True,
        "asset_id": asset_id,
        "asset_file": str(
            asset_file
        ),
        "registry_version":
            registry_version,
        "finalized_at":
            "2026-09-08T00:03:00+00:00",
    }

    path.write_text(
        json.dumps(
            record,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return path, record


def owner_entries(
    project_path,
    task_id=TASK_ID,
):
    return [
        entry
        for entry in read_registry(
            project_path
        )
        if (
            entry.get(
                "generation_context",
                {},
            ).get("task_id")
            == task_id
        )
    ]


def versions_for_asset(
    project_path,
    asset_id,
):
    root = (
        Path(project_path)
        / "assets"
        / "versions"
        / asset_id
    )

    if not root.exists():
        return []

    return sorted(
        root.glob("v*/asset.json")
    )


def resolve_recorded_asset_file(
    project_path,
    value,
):
    path = Path(value)

    if not path.is_absolute():
        path = (
            Path(project_path)
            / path
        )

    return path


def assert_sources_unchanged(
    paths,
    source_bytes,
):
    for name, path in paths.items():
        assert path.read_bytes() == (
            source_bytes[name]
        )


def assert_context_unchanged(
    context,
):
    assert (
        context["generation"].read_bytes()
        == context["generation_bytes"]
    )
    assert (
        context["render"].read_bytes()
        == context["render_bytes"]
    )


def assert_no_finalized(
    project_path,
):
    assert not finalized_path(
        project_path
    ).exists()


def assert_no_logical_asset(
    project_path,
):
    assert not canonical_asset_file(
        project_path
    ).exists()
    assert owner_entries(
        project_path
    ) == []


def assert_materialized(
    project_path,
    outcome,
    expected_asset_id,
):
    path = finalized_path(
        project_path
    )
    assert path.is_file()

    durable = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert outcome == durable

    assert durable["format_version"] == 1
    assert durable["task_id"] == TASK_ID
    assert durable["task_type"] == TASK_TYPE
    assert durable["job_id"] == JOB_ID
    assert durable["provider"] == PROVIDER
    assert durable["metadata"] == {
        "scene_id": SCENE_ID,
        "shot_id": SHOT_ID,
    }
    assert (
        durable["result_state"]
        == "finalized"
    )
    assert durable["asset_ready"] is True
    assert (
        durable["asset_id"]
        == expected_asset_id
    )
    assert isinstance(
        durable["registry_version"],
        int,
    )
    assert (
        durable["registry_version"]
        >= 1
    )
    assert isinstance(
        durable["finalized_at"],
        str,
    )
    assert durable["finalized_at"]

    asset_path = canonical_asset_file(
        project_path
    )
    assert asset_path.is_file()

    recorded_asset_path = (
        resolve_recorded_asset_file(
            project_path,
            durable["asset_file"],
        )
    )
    assert (
        recorded_asset_path.resolve()
        == asset_path.resolve()
    )

    asset = json.loads(
        asset_path.read_text(
            encoding="utf-8"
        )
    )

    assert asset["asset_id"] == (
        expected_asset_id
    )
    assert asset["type"] == TASK_TYPE
    assert asset["provider"] == PROVIDER
    assert asset["metadata"][
        "scene_id"
    ] == SCENE_ID
    assert asset["metadata"][
        "shot_id"
    ] == SHOT_ID

    owners = owner_entries(
        project_path
    )
    assert len(owners) == 1

    owner = owners[0]

    assert owner["asset_id"] == (
        expected_asset_id
    )
    assert owner[
        "generation_context"
    ] == generation_context()

    assert owner["version"] == (
        durable["registry_version"]
    )

    version_path = version_file(
        project_path,
        expected_asset_id,
        durable["registry_version"],
    )
    assert version_path.is_file()

    version_data = json.loads(
        version_path.read_text(
            encoding="utf-8"
        )
    )

    assert version_data["asset_id"] == (
        expected_asset_id
    )
    assert version_data[
        "generation_context"
    ] == generation_context()

    assert len(
        versions_for_asset(
            project_path,
            expected_asset_id,
        )
    ) == 1

    return durable


def test_successful_retrieved_result_creates_one_durable_asset(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    outcome = lifecycle.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        outcome,
        TASK_ID,
    )

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )

    retrieved = json.loads(
        paths["retrieved"].read_text(
            encoding="utf-8"
        )
    )
    assert retrieved["asset_ready"] is False
    assert (
        retrieved["result_state"]
        == "retrieved"
    )


def test_finalized_restart_is_idempotent(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    first = lifecycle.finalize_once(
        TASK_ID
    )

    durable_path = finalized_path(
        tmp_path
    )
    asset_path = canonical_asset_file(
        tmp_path
    )
    registry = registry_path(
        tmp_path
    )
    version = version_file(
        tmp_path,
        TASK_ID,
        first["registry_version"],
    )

    before = {
        "finalized":
            durable_path.read_bytes(),
        "asset":
            asset_path.read_bytes(),
        "registry":
            registry.read_bytes(),
        "version":
            version.read_bytes(),
    }

    restarted_repository = (
        GenerationJobRepository(
            tmp_path
        )
    )
    _, restarted, _ = build_lifecycle(
        restarted_repository
    )

    second = restarted.finalize_once(
        TASK_ID
    )

    assert second == first
    assert (
        durable_path.read_bytes()
        == before["finalized"]
    )
    assert (
        asset_path.read_bytes()
        == before["asset"]
    )
    assert (
        registry.read_bytes()
        == before["registry"]
    )
    assert (
        version.read_bytes()
        == before["version"]
    )

    assert len(
        owner_entries(tmp_path)
    ) == 1
    assert len(
        versions_for_asset(
            tmp_path,
            TASK_ID,
        )
    ) == 1

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    "partial_state",
    [
        "registry_without_asset",
        "asset_without_registry",
        "version_without_registry_or_asset",
    ],
)
def test_partial_local_state_is_repaired_without_duplicate(
    tmp_path,
    partial_state,
):
    (
        repository,
        _,
        retrieved,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    entry = make_registry_entry(
        TASK_ID
    )

    if (
        partial_state
        == "registry_without_asset"
    ):
        write_registry(
            tmp_path,
            [entry],
        )
        write_version(
            tmp_path,
            entry,
        )

    elif (
        partial_state
        == "asset_without_registry"
    ):
        write_asset(
            tmp_path,
            TASK_ID,
            entry,
            retrieved["provider_result"],
        )

    else:
        write_version(
            tmp_path,
            entry,
        )

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    outcome = lifecycle.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        outcome,
        TASK_ID,
    )

    assert len(
        owner_entries(tmp_path)
    ) == 1
    assert len(
        versions_for_asset(
            tmp_path,
            TASK_ID,
        )
    ) == 1

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_conflicting_preexisting_asset_for_same_task_is_rejected(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    conflict_entry = (
        make_registry_entry(
            "wrong-asset-id"
        )
    )

    asset_path = write_asset(
        tmp_path,
        "wrong-asset-id",
        conflict_entry,
    )
    before = asset_path.read_bytes()

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(asset|conflict|ownership|identity)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert (
        asset_path.read_bytes()
        == before
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_missing_retrieved_record_fails_before_asset_mutation(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    paths["retrieved"].unlink()
    paths.pop("retrieved")
    source_bytes.pop("retrieved")

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(retriev|missing|record|result)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_finalized(
        tmp_path
    )
    assert_no_logical_asset(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    "malformed",
    [
        b"{not-json",
        (
            json.dumps(
                {
                    "format_version": 1,
                    "task_id": TASK_ID,
                }
            )
            + "\n"
        ).encode("utf-8"),
    ],
)
def test_malformed_retrieved_record_fails_before_asset_mutation(
    tmp_path,
    malformed,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    paths["retrieved"].write_bytes(
        malformed
    )
    source_bytes["retrieved"] = (
        malformed
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(retriev|record|corrupt|invalid|field)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_finalized(
        tmp_path
    )
    assert_no_logical_asset(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    (
        "target_record",
        "field",
        "value",
    ),
    [
        (
            "terminal",
            "task_type",
            "image",
        ),
        (
            "terminal",
            "provider",
            "different-provider",
        ),
        (
            "terminal",
            "job_id",
            "different-job",
        ),
        (
            "terminal",
            "metadata",
            {
                "scene_id": SCENE_ID,
                "shot_id": 999,
            },
        ),
        (
            "retrieved",
            "task_type",
            "image",
        ),
        (
            "retrieved",
            "provider",
            "different-provider",
        ),
        (
            "retrieved",
            "job_id",
            "different-job",
        ),
        (
            "retrieved",
            "metadata",
            {
                "scene_id": SCENE_ID,
                "shot_id": 999,
            },
        ),
    ],
)
def test_source_identity_mismatch_is_rejected_before_asset_mutation(
    tmp_path,
    target_record,
    field,
    value,
):
    terminal_overrides = None
    retrieved_overrides = None

    if target_record == "terminal":
        terminal_overrides = {
            field: value
        }
    else:
        retrieved_overrides = {
            field: value
        }

    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        terminal_overrides=(
            terminal_overrides
        ),
        retrieved_overrides=(
            retrieved_overrides
        ),
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(identity|mismatch|metadata|"
            "provider|job|task)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_finalized(
        tmp_path
    )
    assert_no_logical_asset(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_missing_generation_result_fails_before_asset_mutation(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
    ) = create_source_chain(
        tmp_path
    )

    render_path = write_render_plan(
        tmp_path
    )
    render_before = (
        render_path.read_bytes()
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(generation_result|scene|context|missing)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_logical_asset(
        tmp_path
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert (
        render_path.read_bytes()
        == render_before
    )


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "duplicate",
    ],
)
def test_scene_task_snapshot_cardinality_must_be_exactly_one(
    tmp_path,
    mode,
):
    if mode == "missing":
        tasks = [
            make_task_snapshot(
                task_id="other-task"
            )
        ]
    else:
        tasks = [
            make_task_snapshot(),
            make_task_snapshot(),
        ]

    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        tasks=tasks,
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(task|scene|duplicate|missing|exact)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_logical_asset(
        tmp_path
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    (
        "field",
        "snapshot",
    ),
    [
        (
            "type",
            make_task_snapshot(
                task_type="image"
            ),
        ),
        (
            "provider",
            make_task_snapshot(
                provider="different-provider"
            ),
        ),
        (
            "scene_id",
            make_task_snapshot(
                scene_id=999
            ),
        ),
        (
            "shot_id",
            make_task_snapshot(
                shot_id=999
            ),
        ),
    ],
)
def test_scene_task_snapshot_identity_cannot_override_durable_identity(
    tmp_path,
    field,
    snapshot,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        tasks=[snapshot],
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(identity|mismatch|provider|"
            "type|scene|shot)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_logical_asset(
        tmp_path
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_missing_render_plan_fails_before_asset_mutation(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
    ) = create_source_chain(
        tmp_path
    )

    generation_path = (
        write_generation_result(
            tmp_path
        )
    )
    generation_before = (
        generation_path.read_bytes()
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(render_plan|render|shot|missing)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_logical_asset(
        tmp_path
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert (
        generation_path.read_bytes()
        == generation_before
    )


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "duplicate",
    ],
)
def test_render_plan_shot_cardinality_must_be_exactly_one(
    tmp_path,
    mode,
):
    if mode == "missing":
        shots = [
            make_shot(
                shot_id=999
            )
        ]
    else:
        shots = [
            make_shot(),
            make_shot(),
        ]

    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        shots=shots,
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(shot|render|duplicate|missing|exact)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_logical_asset(
        tmp_path
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_missing_provider_asset_id_falls_back_to_task_id(
    tmp_path,
):
    payload = provider_result()

    assert "asset_id" not in payload

    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        provider_payload=payload,
    )

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    outcome = lifecycle.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        outcome,
        TASK_ID,
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_valid_supplied_asset_id_is_preserved(
    tmp_path,
):
    supplied = "provider-asset-001"

    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        provider_payload=(
            provider_result(
                asset_id_marker=True,
                asset_id=supplied,
            )
        ),
    )

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    outcome = lifecycle.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        outcome,
        supplied,
    )

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    "bad_asset_id",
    [
        None,
        "",
        123,
        ".",
        "..",
        "/absolute",
        "../escape",
        "folder/asset",
        "folder\\asset",
    ],
)
def test_invalid_supplied_asset_id_is_rejected_without_normalization(
    tmp_path,
    bad_asset_id,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        provider_payload=(
            provider_result(
                asset_id_marker=True,
                asset_id=bad_asset_id,
            )
        ),
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(asset_id|asset|path|safe|invalid)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_logical_asset(
        tmp_path
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_supplied_asset_id_owned_by_other_task_is_rejected(
    tmp_path,
):
    supplied = "shared-asset"

    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(
        tmp_path,
        provider_payload=(
            provider_result(
                asset_id_marker=True,
                asset_id=supplied,
            )
        ),
    )

    other_entry = make_registry_entry(
        supplied,
        task_id="other-task",
        job_id="other-job",
    )

    reg_path = write_registry(
        tmp_path,
        [other_entry],
    )
    version_path_existing = (
        write_version(
            tmp_path,
            other_entry,
        )
    )

    registry_before = (
        reg_path.read_bytes()
    )
    version_before = (
        version_path_existing.read_bytes()
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(asset|ownership|owner|conflict|task)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert (
        reg_path.read_bytes()
        == registry_before
    )
    assert (
        version_path_existing.read_bytes()
        == version_before
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_multiple_registry_entries_for_one_task_are_rejected(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    entries = [
        make_registry_entry(
            "asset-one"
        ),
        make_registry_entry(
            "asset-two"
        ),
    ]

    reg_path = write_registry(
        tmp_path,
        entries,
    )
    before = reg_path.read_bytes()

    for entry in entries:
        write_version(
            tmp_path,
            entry,
        )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(registry|duplicate|task|ownership|multiple)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert (
        reg_path.read_bytes()
        == before
    )
    assert_no_finalized(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_storage_failure_returns_explicit_error_without_finalized_record(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    def fail_storage(
        self,
        *args,
        **kwargs,
    ):
        raise OSError(
            "deterministic Stage 2K "
            "asset storage failure"
        )

    monkeypatch.setattr(
        AIResultStorage,
        "save_retrieved_result",
        fail_storage,
        raising=False,
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(asset|storage|finaliz|persist|failure)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_finalized(
        tmp_path
    )
    assert not canonical_asset_file(
        tmp_path
    ).exists()
    assert owner_entries(
        tmp_path
    ) == []

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_finalized_record_write_failure_is_locally_recoverable_without_duplication(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    def fail_finalized_write(
        record,
    ):
        raise GenerationJobPersistenceError(
            "deterministic finalized "
            "record write failure"
        )

    monkeypatch.setattr(
        repository,
        "persist_finalized",
        fail_finalized_write,
        raising=False,
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(finaliz|persist|durable|write)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_finalized(
        tmp_path
    )

    assert canonical_asset_file(
        tmp_path
    ).is_file()

    owners_after_failure = (
        owner_entries(
            tmp_path
        )
    )
    assert len(
        owners_after_failure
    ) == 1

    asset_id = (
        owners_after_failure[0][
            "asset_id"
        ]
    )

    versions_after_failure = (
        versions_for_asset(
            tmp_path,
            asset_id,
        )
    )
    assert len(
        versions_after_failure
    ) == 1

    restarted_repository = (
        GenerationJobRepository(
            tmp_path
        )
    )
    _, restarted, _ = build_lifecycle(
        restarted_repository
    )

    outcome = restarted.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        outcome,
        asset_id,
    )

    assert len(
        owner_entries(tmp_path)
    ) == 1
    assert len(
        versions_for_asset(
            tmp_path,
            asset_id,
        )
    ) == 1

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    "observer",
    [
        "audit",
        "events",
    ],
)
def test_observability_failure_cannot_destroy_finalized_state(
    tmp_path,
    observer,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    _, lifecycle, _ = build_lifecycle(
        repository,
        audit=(
            FailingAudit()
            if observer == "audit"
            else None
        ),
        events=(
            FailingEvents()
            if observer == "events"
            else None
        ),
    )

    first = lifecycle.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        first,
        first["asset_id"],
    )

    registry_before = (
        registry_path(
            tmp_path
        ).read_bytes()
    )
    finalized_before = (
        finalized_path(
            tmp_path
        ).read_bytes()
    )

    second = lifecycle.finalize_once(
        TASK_ID
    )

    assert second == first
    assert (
        registry_path(
            tmp_path
        ).read_bytes()
        == registry_before
    )
    assert (
        finalized_path(
            tmp_path
        ).read_bytes()
        == finalized_before
    )

    assert len(
        owner_entries(tmp_path)
    ) == 1
    assert len(
        versions_for_asset(
            tmp_path,
            first["asset_id"],
        )
    ) == 1

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_generation_result_and_render_plan_remain_byte_identical(
    tmp_path,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    lifecycle.finalize_once(
        TASK_ID
    )

    assert_context_unchanged(
        context
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )


def test_stage_2k_does_not_call_stage_2j_or_network(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    def forbidden_retrieval(
        self,
        task_id,
    ):
        raise AssertionError(
            "Stage 2K must not call "
            "GenerationJobResultLifecycle.retrieve_once"
        )

    monkeypatch.setattr(
        GenerationJobResultLifecycle,
        "retrieve_once",
        forbidden_retrieval,
    )

    def forbidden_connect(
        self,
        address,
    ):
        raise AssertionError(
            "Stage 2K must not access network"
        )

    monkeypatch.setattr(
        socket.socket,
        "connect",
        forbidden_connect,
    )

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    outcome = lifecycle.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        outcome,
        outcome["asset_id"],
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_stage_2k_does_not_construct_fake_generation_task(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    def forbidden_task_init(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Stage 2K must not reconstruct "
            "a fake GenerationTask"
        )

    monkeypatch.setattr(
        GenerationTask,
        "__init__",
        forbidden_task_init,
    )

    _, lifecycle, _ = (
        build_lifecycle(repository)
    )

    outcome = lifecycle.finalize_once(
        TASK_ID
    )

    assert_materialized(
        tmp_path,
        outcome,
        outcome["asset_id"],
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    "malformed",
    [
        b"{not-json",
        (
            json.dumps(
                {
                    "format_version": 1,
                    "task_id": TASK_ID,
                }
            )
            + "\n"
        ).encode("utf-8"),
    ],
)
def test_malformed_finalized_record_is_explicit_error_without_asset_mutation(
    tmp_path,
    malformed,
):
    (
        repository,
        _,
        _,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    path = finalized_path(
        tmp_path
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_bytes(
        malformed
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(finaliz|record|corrupt|invalid|field)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert (
        path.read_bytes()
        == malformed
    )
    assert_no_logical_asset(
        tmp_path
    )
    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


@pytest.mark.parametrize(
    "missing_component",
    [
        "asset",
        "registry",
        "version",
    ],
)
def test_stale_finalized_record_is_never_silently_returned(
    tmp_path,
    missing_component,
):
    (
        repository,
        _,
        retrieved,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    asset_id = TASK_ID
    entry = make_registry_entry(
        asset_id
    )

    if missing_component != "asset":
        write_asset(
            tmp_path,
            asset_id,
            entry,
            retrieved["provider_result"],
        )

    if missing_component != "registry":
        write_registry(
            tmp_path,
            [entry],
        )

    if missing_component != "version":
        write_version(
            tmp_path,
            entry,
        )

    path, stale = (
        write_finalized_record(
            tmp_path,
            asset_id=asset_id,
            registry_version=1,
        )
    )

    stale_before = path.read_bytes()

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    outcome = None
    failed = False

    try:
        outcome = lifecycle.finalize_once(
            TASK_ID
        )
    except lifecycle_error:
        failed = True

    if failed:
        # Explicit error is allowed by the
        # approved Stage 2K architecture.
        assert (
            path.read_bytes()
            == stale_before
        )
        assert len(
            owner_entries(tmp_path)
        ) <= 1
        assert len(
            versions_for_asset(
                tmp_path,
                asset_id,
            )
        ) <= 1
    else:
        # Safe repair is also allowed, but it
        # must restore one coherent logical
        # asset without duplication.
        assert outcome is not None
        assert_materialized(
            tmp_path,
            outcome,
            asset_id,
        )

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_stale_finalized_record_with_conflicting_ownership_is_rejected(
    tmp_path,
):
    (
        repository,
        _,
        retrieved,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    asset_id = "shared-asset"

    conflicting_entry = (
        make_registry_entry(
            asset_id,
            task_id="other-task",
            job_id="other-job",
        )
    )

    asset_path = write_asset(
        tmp_path,
        asset_id,
        conflicting_entry,
        retrieved["provider_result"],
    )
    registry = write_registry(
        tmp_path,
        [conflicting_entry],
    )
    version = write_version(
        tmp_path,
        conflicting_entry,
    )
    finalized, _ = (
        write_finalized_record(
            tmp_path,
            asset_id=asset_id,
            registry_version=1,
        )
    )

    before = {
        "asset":
            asset_path.read_bytes(),
        "registry":
            registry.read_bytes(),
        "version":
            version.read_bytes(),
        "finalized":
            finalized.read_bytes(),
    }

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(ownership|owner|conflict|"
            "finaliz|task|asset)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert (
        asset_path.read_bytes()
        == before["asset"]
    )
    assert (
        registry.read_bytes()
        == before["registry"]
    )
    assert (
        version.read_bytes()
        == before["version"]
    )
    assert (
        finalized.read_bytes()
        == before["finalized"]
    )

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_consistency_is_verified_before_finalized_record_is_persisted(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        _,
        retrieved,
        paths,
        source_bytes,
        context,
    ) = prepare_full(tmp_path)

    def incomplete_storage(
        self,
        *args,
        **kwargs,
    ):
        asset_id = TASK_ID
        entry = make_registry_entry(
            asset_id
        )

        asset_path = write_asset(
            tmp_path,
            asset_id,
            entry,
            retrieved["provider_result"],
        )
        write_registry(
            tmp_path,
            [entry],
        )

        # Deliberately omit the version file.
        return asset_path

    monkeypatch.setattr(
        AIResultStorage,
        "save_retrieved_result",
        incomplete_storage,
        raising=False,
    )

    _, lifecycle, lifecycle_error = (
        build_lifecycle(repository)
    )

    with pytest.raises(
        lifecycle_error,
        match=(
            "(?i)"
            "(version|consistent|registry|"
            "asset|finaliz)"
        ),
    ):
        lifecycle.finalize_once(
            TASK_ID
        )

    assert_no_finalized(
        tmp_path
    )

    assert_sources_unchanged(
        paths,
        source_bytes,
    )
    assert_context_unchanged(
        context
    )


def test_repository_exposes_durable_finalized_phase_contract(
    tmp_path,
):
    repository = GenerationJobRepository(
        tmp_path
    )

    lifecycle_contract()

    for method_name in (
        "finalized_path",
        "finalized_exists",
        "load_finalized",
        "persist_finalized",
    ):
        assert callable(
            getattr(
                repository,
                method_name,
                None,
            )
        ), (
            "Stage 2K repository must expose "
            f"{method_name}(...)"
        )
