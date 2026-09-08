import importlib
import json
import socket
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.ai_core.asset_registry import AssetRegistry
from core.ai_core.generation_job_asset_lifecycle import (
    GenerationJobAssetLifecycle,
)
from core.ai_core.generation_job_lifecycle import (
    GenerationJobLifecycle,
)
from core.ai_core.generation_job_repository import (
    GenerationJobRepository,
)
from core.ai_core.generation_job_result_lifecycle import (
    GenerationJobResultLifecycle,
)
from core.ai_core.generation_queue import GenerationTask
from core.ai_core.result_storage import AIResultStorage

import core.movie_engine.generation_engine as generation_engine_module
from core.movie_engine.generation_engine import GenerationEngine


RECONCILER_MODULE = (
    "core.movie_engine.generation_result_reconciler"
)
STATUS_MODULE = (
    "core.movie_engine.generation_status"
)

TASK_ID = "task-2l-001"
JOB_ID = "job-2l-001"
PROVIDER = "deterministic-remote-video"
TASK_TYPE = "video"
SCENE_ID = 1
SHOT_ID = 2
ASSET_ID = "asset-2l-001"
REGISTRY_VERSION = 1


class FailingAudit:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.calls = 0
        self.observed_document = None

    def record(self, event, data):
        self.calls += 1

        document = read_generation(
            self.project_path
        )
        self.observed_document = document
        task = matching_task(document)

        assert task["status"] == "done"
        assert document["status"] == "completed"
        assert (
            task["output"]
            == completion_overlay()["asset_file"]
        )

        for key, value in completion_overlay().items():
            assert task["result"][key] == value

        raise OSError(
            "deterministic Stage 2L audit failure"
        )


class FailingEvents:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.calls = 0
        self.observed_document = None

    def emit(self, event, data):
        self.calls += 1

        document = read_generation(
            self.project_path
        )
        self.observed_document = document
        task = matching_task(document)

        assert task["status"] == "done"
        assert document["status"] == "completed"
        assert (
            task["output"]
            == completion_overlay()["asset_file"]
        )

        for key, value in completion_overlay().items():
            assert task["result"][key] == value

        raise OSError(
            "deterministic Stage 2L event failure"
        )


def contracts():
    try:
        status_module = importlib.import_module(
            STATUS_MODULE
        )
    except ModuleNotFoundError as exc:
        if exc.name != STATUS_MODULE:
            raise

        pytest.fail(
            "Stage 2L shared aggregation module is missing: "
            "expected core.movie_engine.generation_status",
            pytrace=False,
        )

    aggregate = getattr(
        status_module,
        "aggregate_generation_tasks",
        None,
    )

    if not callable(aggregate):
        pytest.fail(
            "Stage 2L requires pure shared "
            "aggregate_generation_tasks(tasks)",
            pytrace=False,
        )

    try:
        module = importlib.import_module(
            RECONCILER_MODULE
        )
    except ModuleNotFoundError as exc:
        if exc.name != RECONCILER_MODULE:
            raise

        pytest.fail(
            "Stage 2L reconciliation lifecycle is missing: "
            "expected "
            "core.movie_engine.generation_result_reconciler "
            "with GenerationResultReconciler.reconcile_once(task_id)",
            pytrace=False,
        )

    reconciler_type = getattr(
        module,
        "GenerationResultReconciler",
        None,
    )
    reconciler_error = getattr(
        module,
        "GenerationResultReconciliationError",
        None,
    )

    if (
        reconciler_type is None
        or reconciler_error is None
    ):
        pytest.fail(
            "Stage 2L reconciliation public contract "
            "is incomplete",
            pytrace=False,
        )

    return (
        status_module,
        aggregate,
        module,
        reconciler_type,
        reconciler_error,
    )


def build_reconciler(
    repository,
    audit=None,
    events=None,
):
    (
        status_module,
        aggregate,
        module,
        reconciler_type,
        reconciler_error,
    ) = contracts()

    reconciler = reconciler_type(
        job_repository=repository,
        audit=audit,
        events=events,
    )

    assert callable(
        getattr(
            reconciler,
            "reconcile_once",
            None,
        )
    )

    return (
        status_module,
        aggregate,
        module,
        reconciler,
        reconciler_error,
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


def provider_result():
    return {
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "remote_artifact": {
            "opaque": True,
            "do_not_copy_to_generation_result": True,
        },
    }


def canonical_asset_file(
    project_path,
):
    return (
        Path(project_path)
        / "assets"
        / TASK_TYPE
        / f"scene_{SCENE_ID:03d}"
        / f"shot_{SHOT_ID:03d}"
        / "asset.json"
    )


def registry_path(project_path):
    return (
        Path(project_path)
        / "assets"
        / "registry.json"
    )


def version_file(project_path):
    return (
        Path(project_path)
        / "assets"
        / "versions"
        / ASSET_ID
        / f"v{REGISTRY_VERSION:03d}"
        / "asset.json"
    )


def finalized_path(project_path):
    return (
        Path(project_path)
        / "generation_jobs"
        / "finalized"
        / f"{TASK_ID}.json"
    )


def generation_result_path(
    project_path,
):
    return (
        Path(project_path)
        / "render_output"
        / f"scene_{SCENE_ID:03d}"
        / "generation_result.json"
    )


def render_plan_path(project_path):
    return (
        Path(project_path)
        / "render"
        / f"scene_{SCENE_ID:03d}"
        / "render_plan.json"
    )


def make_registry_entry():
    return {
        "asset_id": ASSET_ID,
        "type": TASK_TYPE,
        "provider": PROVIDER,
        "model": {
            "selected_model": {
                "name": "remote-model",
            },
        },
        "quality": "4k",
        "routing": {},
        "provider_capabilities": {},
        "generation_context":
            generation_context(),
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "status": "generated",
        "version": REGISTRY_VERSION,
        "created":
            "2026-09-08T12:00:00",
    }


def make_asset_payload():
    entry = make_registry_entry()

    return {
        "asset_id": ASSET_ID,
        "type": TASK_TYPE,
        "prompt": "Stage 2L finalized asset",
        "provider": PROVIDER,
        "model": {
            "selected_model": {
                "name": "remote-model",
            },
        },
        "quality": "4k",
        "status": "generated",
        "created":
            "2026-09-08T12:00:00",
        "registry": entry,
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "generation_context":
            generation_context(),
        "result":
            provider_result(),
    }


def write_physical_asset_state(
    project_path,
):
    project_path = Path(project_path)

    asset = canonical_asset_file(
        project_path
    )
    asset.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    asset.write_text(
        json.dumps(
            make_asset_payload(),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    registry = registry_path(
        project_path
    )
    registry.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    registry.write_text(
        json.dumps(
            [make_registry_entry()],
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    version = version_file(
        project_path
    )
    version.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    version.write_text(
        json.dumps(
            make_registry_entry(),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    render = render_plan_path(
        project_path
    )
    render.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    render.write_text(
        json.dumps(
            {
                "scene_id": SCENE_ID,
                "shots": [
                    {
                        "shot_id": SHOT_ID,
                        "director_prompt":
                            "Stage 2L read-only render plan",
                    }
                ],
                "stage_2l_preserve":
                    "render-plan-byte-contract",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "asset": asset,
        "registry": registry,
        "version": version,
        "render_plan": render,
    }


def create_job_chain(
    project_path,
):
    repository = GenerationJobRepository(
        project_path
    )

    task = GenerationTask(
        task_type=TASK_TYPE,
        prompt="Stage 2L async shot",
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

    repository.persist_terminal(
        {
            "format_version":
                repository.FORMAT_VERSION,
            "task_id": TASK_ID,
            "task_type": TASK_TYPE,
            "job_id": JOB_ID,
            "provider": PROVIDER,
            "status": "succeeded",
            "metadata": {
                "scene_id": SCENE_ID,
                "shot_id": SHOT_ID,
            },
            "terminal_at":
                "2026-09-08T12:01:00+00:00",
            "result_state":
                "pending_retrieval",
            "asset_ready":
                False,
        }
    )

    repository.persist_retrieved(
        {
            "format_version":
                repository.FORMAT_VERSION,
            "task_id": TASK_ID,
            "task_type": TASK_TYPE,
            "job_id": JOB_ID,
            "provider": PROVIDER,
            "metadata": {
                "scene_id": SCENE_ID,
                "shot_id": SHOT_ID,
            },
            "result_state":
                "retrieved",
            "asset_ready":
                False,
            "provider_result":
                provider_result(),
            "retrieved_at":
                "2026-09-08T12:02:00+00:00",
        }
    )

    repository.persist_finalized(
        {
            "format_version":
                repository.FORMAT_VERSION,
            "task_id": TASK_ID,
            "task_type": TASK_TYPE,
            "job_id": JOB_ID,
            "provider": PROVIDER,
            "metadata": {
                "scene_id": SCENE_ID,
                "shot_id": SHOT_ID,
            },
            "result_state":
                "finalized",
            "asset_ready":
                True,
            "asset_id":
                ASSET_ID,
            "asset_file": str(
                canonical_asset_file(
                    project_path
                ).relative_to(
                    Path(project_path)
                )
            ),
            "registry_version":
                REGISTRY_VERSION,
            "finalized_at":
                "2026-09-08T12:03:00+00:00",
        }
    )

    return repository


def completion_overlay():
    return {
        "status": "done",
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "asset_id": ASSET_ID,
        "asset_ready": True,
        "result_state": "finalized",
        "asset_file": str(
            Path("assets")
            / TASK_TYPE
            / f"scene_{SCENE_ID:03d}"
            / f"shot_{SHOT_ID:03d}"
            / "asset.json"
        ),
        "registry_version":
            REGISTRY_VERSION,
    }


def make_task_snapshot(
    *,
    task_id=TASK_ID,
    status="submitted",
    task_type=TASK_TYPE,
    provider=PROVIDER,
    scene_id=SCENE_ID,
    shot_id=SHOT_ID,
    result_marker="default",
    output=None,
    quality="4k",
):
    if result_marker == "default":
        result = {
            "status": status,
            "job_id": JOB_ID,
            "provider": provider,
            "preserve_me":
                "existing-result-field",
        }
    else:
        result = result_marker

    return {
        "task_id": task_id,
        "type": task_type,
        "status": status,
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
            "preserve_metadata":
                "immutable-stage-2l",
        },
        "result": result,
        "provider": provider,
        "quality": quality,
        "output": output,
        "preserve_task_field":
            "task-snapshot-future-field",
    }


def already_done_task():
    result = {
        "preserve_me":
            "existing-result-field",
        **completion_overlay(),
    }

    return make_task_snapshot(
        status="done",
        result_marker=result,
        output=completion_overlay()[
            "asset_file"
        ],
    )


def write_generation_result(
    project_path,
    *,
    tasks=None,
    scene_id=SCENE_ID,
    extra=None,
):
    path = generation_result_path(
        project_path
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if tasks is None:
        tasks = [
            make_task_snapshot()
        ]

    document = {
        "scene_id": scene_id,
        "created":
            "2026-09-08T11:59:00",
        "quality": "4k",
        "requested_quality": {
            "resolution": "3840x2160",
        },
        "actual_quality": {
            "resolution": "3840x2160",
        },
        "generated": 0,
        "failed": 0,
        "cancelled": 0,
        "submitted": sum(
            1
            for task in tasks
            if (
                isinstance(task, dict)
                and task.get("status")
                == "submitted"
            )
        ),
        "running": sum(
            1
            for task in tasks
            if (
                isinstance(task, dict)
                and task.get("status")
                == "running"
            )
        ),
        "pending": sum(
            1
            for task in tasks
            if (
                isinstance(task, dict)
                and task.get("status")
                not in (
                    "done",
                    "failed",
                    "cancelled",
                )
            )
        ),
        "status": "pending",
        "tasks": tasks,
        "future_top_level_field": {
            "must": "survive",
        },
    }

    if extra:
        document.update(
            extra
        )

    path.write_text(
        json.dumps(
            document,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return path


def prepare_case(
    project_path,
    *,
    tasks=None,
    scene_id=SCENE_ID,
):
    repository = create_job_chain(
        project_path
    )
    physical = write_physical_asset_state(
        project_path
    )
    generation = write_generation_result(
        project_path,
        tasks=tasks,
        scene_id=scene_id,
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
        "finalized":
            repository.finalized_path(
                TASK_ID
            ),
        "generation_result":
            generation,
        **physical,
    }

    before = {
        name: path.read_bytes()
        for name, path in paths.items()
    }

    return (
        repository,
        paths,
        before,
    )


def read_generation(project_path):
    return json.loads(
        generation_result_path(
            project_path
        ).read_text(
            encoding="utf-8"
        )
    )


def matching_task(document):
    matches = [
        task
        for task in document["tasks"]
        if task.get("task_id") == TASK_ID
    ]
    assert len(matches) == 1
    return matches[0]


def assert_job_records_unchanged(
    paths,
    before,
):
    for name in (
        "submitted",
        "terminal",
        "retrieved",
        "finalized",
    ):
        assert (
            paths[name].read_bytes()
            == before[name]
        )


def assert_physical_state_unchanged(
    paths,
    before,
):
    for name in (
        "asset",
        "registry",
        "version",
        "render_plan",
    ):
        assert (
            paths[name].read_bytes()
            == before[name]
        )


def assert_no_scene_mutation(
    paths,
    before,
):
    assert (
        paths[
            "generation_result"
        ].read_bytes()
        == before[
            "generation_result"
        ]
    )


def reconcile(
    repository,
    audit=None,
    events=None,
):
    (
        _,
        _,
        _,
        reconciler,
        _,
    ) = build_reconciler(
        repository,
        audit=audit,
        events=events,
    )

    return reconciler.reconcile_once(
        TASK_ID
    )


def test_submitted_task_reconciles_to_local_done_and_completed_scene(
    tmp_path,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    reconcile(repository)

    document = read_generation(
        tmp_path
    )
    task = matching_task(
        document
    )

    assert task["status"] == "done"
    assert (
        task["output"]
        == completion_overlay()[
            "asset_file"
        ]
    )

    for key, value in (
        completion_overlay().items()
    ):
        assert (
            task["result"][key]
            == value
        )

    assert (
        task["result"][
            "preserve_me"
        ]
        == "existing-result-field"
    )

    assert document["generated"] == 1
    assert document["failed"] == 0
    assert document["cancelled"] == 0
    assert document["submitted"] == 0
    assert document["running"] == 0
    assert document["pending"] == 0
    assert document["status"] == "completed"

    assert_job_records_unchanged(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


@pytest.mark.parametrize(
    (
        "other_status",
        "expected",
    ),
    [
        (
            "submitted",
            {
                "generated": 1,
                "failed": 0,
                "cancelled": 0,
                "submitted": 1,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            "failed",
            {
                "generated": 1,
                "failed": 1,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 0,
                "status":
                    "completed_with_errors",
            },
        ),
        (
            "cancelled",
            {
                "generated": 1,
                "failed": 0,
                "cancelled": 1,
                "submitted": 0,
                "running": 0,
                "pending": 0,
                "status":
                    "completed_with_errors",
            },
        ),
    ],
)
def test_scene_reaggregation_after_one_task_reconciles(
    tmp_path,
    other_status,
    expected,
):
    other = make_task_snapshot(
        task_id="other-task",
        status=other_status,
        shot_id=99,
        result_marker={
            "status": other_status,
        },
    )

    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=[
            make_task_snapshot(),
            other,
        ],
    )

    reconcile(repository)

    document = read_generation(
        tmp_path
    )

    for key, value in expected.items():
        assert document[key] == value

    assert_job_records_unchanged(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


def test_missing_finalized_record_is_explicit_error_without_scene_mutation(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    finalized = paths["finalized"]
    finalized.unlink()
    paths.pop("finalized")
    before.pop("finalized")

    original_finalized_exists = (
        repository.finalized_exists
    )
    calls = {
        "finalized_exists": 0,
        "finalize_once": 0,
        "save_retrieved_result": 0,
        "ensure_retrieved_registration": 0,
    }

    def recording_finalized_exists(
        task_id,
    ):
        calls["finalized_exists"] += 1
        return original_finalized_exists(
            task_id
        )

    def forbidden_finalizer(
        self,
        task_id,
    ):
        calls["finalize_once"] += 1
        raise AssertionError(
            "Stage 2L must not invoke Stage 2K finalizer "
            "when finalized is absent"
        )

    def forbidden_storage(
        self,
        *args,
        **kwargs,
    ):
        calls["save_retrieved_result"] += 1
        raise AssertionError(
            "Stage 2L must not trigger "
            "Stage 2K asset materialization"
        )

    def forbidden_registry_repair(
        self,
        *args,
        **kwargs,
    ):
        calls[
            "ensure_retrieved_registration"
        ] += 1
        raise AssertionError(
            "Stage 2L must not trigger "
            "Stage 2K Registry repair"
        )

    monkeypatch.setattr(
        repository,
        "finalized_exists",
        recording_finalized_exists,
    )
    monkeypatch.setattr(
        GenerationJobAssetLifecycle,
        "finalize_once",
        forbidden_finalizer,
    )
    monkeypatch.setattr(
        AIResultStorage,
        "save_retrieved_result",
        forbidden_storage,
    )
    monkeypatch.setattr(
        AssetRegistry,
        "ensure_retrieved_registration",
        forbidden_registry_repair,
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(finaliz|missing|record)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )
    assert calls["finalized_exists"] >= 1
    assert calls["finalize_once"] == 0
    assert calls["save_retrieved_result"] == 0
    assert (
        calls["ensure_retrieved_registration"]
        == 0
    )
    assert not finalized.exists()

    for name in (
        "submitted",
        "terminal",
        "retrieved",
    ):
        assert (
            paths[name].read_bytes()
            == before[name]
        )

    assert_physical_state_unchanged(
        paths,
        before,
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
def test_malformed_finalized_record_is_rejected_without_scene_mutation(
    tmp_path,
    malformed,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    paths["finalized"].write_bytes(
        malformed
    )
    before["finalized"] = malformed

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(finaliz|invalid|corrupt|record|field)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


@pytest.mark.parametrize(
    "missing_component",
    [
        "asset",
        "registry",
        "version",
    ],
)
def test_stale_finalized_state_is_rejected_read_only_without_stage_2k_repair(
    tmp_path,
    monkeypatch,
    missing_component,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    paths[
        missing_component
    ].unlink()

    def forbidden_storage(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Stage 2L must not trigger "
            "Stage 2K asset materialization"
        )

    def forbidden_registry_repair(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Stage 2L must not trigger "
            "Stage 2K Registry repair"
        )

    monkeypatch.setattr(
        AIResultStorage,
        "save_retrieved_result",
        forbidden_storage,
    )

    monkeypatch.setattr(
        AssetRegistry,
        "ensure_retrieved_registration",
        forbidden_registry_repair,
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(finaliz|asset|registry|version|consistent|stale)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )
    assert_job_records_unchanged(
        paths,
        before,
    )


def test_valid_stage_2k_consistency_verification_is_strictly_read_only(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    def forbidden_storage(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Stage 2L must not materialize asset"
        )

    def forbidden_registry_repair(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Stage 2L must not mutate Registry"
        )

    monkeypatch.setattr(
        AIResultStorage,
        "save_retrieved_result",
        forbidden_storage,
    )
    monkeypatch.setattr(
        AssetRegistry,
        "ensure_retrieved_registration",
        forbidden_registry_repair,
    )

    reconcile(repository)

    assert_job_records_unchanged(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


def test_missing_generation_result_is_explicit_error(
    tmp_path,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    paths[
        "generation_result"
    ].unlink()

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(generation_result|scene|missing)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_job_records_unchanged(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


@pytest.mark.parametrize(
    "malformed",
    [
        b"{broken-json",
        b"[]\n",
    ],
)
def test_malformed_generation_result_is_rejected(
    tmp_path,
    malformed,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    paths[
        "generation_result"
    ].write_bytes(
        malformed
    )
    before[
        "generation_result"
    ] = malformed

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(generation_result|invalid|json|scene|document)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


def test_generation_result_scene_identity_must_match_finalized_scene(
    tmp_path,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        scene_id=999,
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(scene|identity|mismatch)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "duplicate",
    ],
)
def test_matching_task_cardinality_must_be_exactly_one(
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
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=tasks,
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(task|duplicate|missing|exact|cardinality)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


@pytest.mark.parametrize(
    "task",
    [
        make_task_snapshot(
            task_type="image"
        ),
        make_task_snapshot(
            provider="wrong-provider"
        ),
        make_task_snapshot(
            scene_id=999
        ),
        make_task_snapshot(
            shot_id=999
        ),
    ],
    ids=[
        "task-type",
        "provider",
        "scene-id",
        "shot-id",
    ],
)
def test_task_snapshot_cannot_override_finalized_identity(
    tmp_path,
    task,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=[task],
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(identity|mismatch|task|provider|scene|shot)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    [
        (
            "job_id",
            "wrong-job",
        ),
        (
            "provider",
            "wrong-provider",
        ),
    ],
)
def test_task_result_identity_if_present_must_match_finalized(
    tmp_path,
    field,
    value,
):
    result = {
        "status": "submitted",
        "job_id": JOB_ID,
        "provider": PROVIDER,
    }
    result[field] = value

    task = make_task_snapshot(
        result_marker=result
    )

    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=[task],
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(result|identity|job|provider|mismatch)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


@pytest.mark.parametrize(
    "status",
    [
        "failed",
        "cancelled",
        "provider_weird_state",
    ],
)
def test_contradictory_or_unknown_task_state_is_not_promoted_to_done(
    tmp_path,
    status,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=[
            make_task_snapshot(
                status=status,
                result_marker={
                    "status": status,
                    "job_id": JOB_ID,
                    "provider": PROVIDER,
                },
            )
        ],
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(status|terminal|failed|cancelled|unknown|contradict)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


def test_task_result_none_may_become_canonical_completion_dictionary(
    tmp_path,
):
    (
        repository,
        _,
        _,
    ) = prepare_case(
        tmp_path,
        tasks=[
            make_task_snapshot(
                result_marker=None
            )
        ],
    )

    reconcile(repository)

    task = matching_task(
        read_generation(
            tmp_path
        )
    )

    assert isinstance(
        task["result"],
        dict,
    )

    for key, value in (
        completion_overlay().items()
    ):
        assert (
            task["result"][key]
            == value
        )


def test_existing_result_dictionary_fields_are_preserved(
    tmp_path,
):
    result = {
        "status": "submitted",
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "custom": {
            "must": "survive",
        },
        "legacy_note": "preserve",
    }

    (
        repository,
        _,
        _,
    ) = prepare_case(
        tmp_path,
        tasks=[
            make_task_snapshot(
                result_marker=result
            )
        ],
    )

    reconcile(repository)

    task = matching_task(
        read_generation(
            tmp_path
        )
    )

    assert task["result"][
        "custom"
    ] == {
        "must": "survive",
    }
    assert task["result"][
        "legacy_note"
    ] == "preserve"

    for key, value in (
        completion_overlay().items()
    ):
        assert (
            task["result"][key]
            == value
        )


@pytest.mark.parametrize(
    "malformed_result",
    [
        "not-a-dict",
        ["bad"],
        123,
        True,
    ],
)
def test_non_dictionary_non_none_task_result_is_rejected_atomically(
    tmp_path,
    malformed_result,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=[
            make_task_snapshot(
                result_marker=(
                    malformed_result
                )
            )
        ],
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(result|dictionary|dict|shape|invalid)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


def test_already_done_consistent_state_is_noop_idempotent(
    tmp_path,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=[
            already_done_task()
        ],
    )

    # Fix top-level aggregation to the already-done
    # canonical state before the idempotency call.
    document = read_generation(
        tmp_path
    )
    document.update(
        {
            "generated": 1,
            "failed": 0,
            "cancelled": 0,
            "submitted": 0,
            "running": 0,
            "pending": 0,
            "status": "completed",
        }
    )
    paths[
        "generation_result"
    ].write_text(
        json.dumps(
            document,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    before[
        "generation_result"
    ] = paths[
        "generation_result"
    ].read_bytes()

    reconcile(repository)

    assert_no_scene_mutation(
        paths,
        before,
    )

    reconcile(repository)

    assert_no_scene_mutation(
        paths,
        before,
    )


@pytest.mark.parametrize(
    "conflict_field",
    [
        "output",
        "status",
        "job_id",
        "provider",
        "asset_id",
        "asset_ready",
        "result_state",
        "asset_file",
        "registry_version",
    ],
)
def test_already_done_complete_overlay_conflict_is_explicit_error(
    tmp_path,
    conflict_field,
):
    task = already_done_task()

    if conflict_field == "output":
        task["output"] = (
            "assets/video/wrong/asset.json"
        )

    elif conflict_field == "status":
        # Still a contradictory local snapshot:
        # durable completion references exist,
        # but status is no longer done.
        task["status"] = "failed"

    else:
        task["result"][
            conflict_field
        ] = "wrong"

        if conflict_field == "asset_ready":
            task["result"][
                conflict_field
            ] = False

        if (
            conflict_field
            == "registry_version"
        ):
            task["result"][
                conflict_field
            ] = 999

    (
        repository,
        paths,
        before,
    ) = prepare_case(
        tmp_path,
        tasks=[task],
    )

    (
        _,
        _,
        _,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(done|completion|identity|conflict|"
            "output|result|status|asset|registry)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )


def test_opaque_provider_result_is_not_copied_into_generation_result(
    tmp_path,
):
    (
        repository,
        _,
        _,
    ) = prepare_case(tmp_path)

    reconcile(repository)

    document = read_generation(
        tmp_path
    )

    serialized = json.dumps(
        document,
        sort_keys=True,
    )

    assert (
        "do_not_copy_to_generation_result"
        not in serialized
    )
    assert (
        "opaque-remote-result"
        not in serialized
    )


def test_task_identity_metadata_quality_and_future_fields_are_preserved(
    tmp_path,
):
    original = make_task_snapshot()

    (
        repository,
        _,
        _,
    ) = prepare_case(
        tmp_path,
        tasks=[original],
    )

    reconcile(repository)

    task = matching_task(
        read_generation(
            tmp_path
        )
    )

    assert task["task_id"] == (
        original["task_id"]
    )
    assert task["type"] == (
        original["type"]
    )
    assert task["provider"] == (
        original["provider"]
    )
    assert task["metadata"] == (
        original["metadata"]
    )
    assert task["quality"] == (
        original["quality"]
    )
    assert task[
        "preserve_task_field"
    ] == (
        original[
            "preserve_task_field"
        ]
    )


def test_unrelated_top_level_generation_result_fields_are_preserved(
    tmp_path,
):
    (
        repository,
        _,
        _,
    ) = prepare_case(tmp_path)

    before_document = (
        read_generation(
            tmp_path
        )
    )

    reconcile(repository)

    after = read_generation(
        tmp_path
    )

    for key in (
        "scene_id",
        "created",
        "quality",
        "requested_quality",
        "actual_quality",
        "future_top_level_field",
    ):
        assert (
            after[key]
            == before_document[key]
        )


def test_all_job_phase_records_remain_byte_identical(
    tmp_path,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    reconcile(repository)

    assert_job_records_unchanged(
        paths,
        before,
    )


def test_asset_registry_version_and_render_plan_remain_byte_identical(
    tmp_path,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    reconcile(repository)

    assert_physical_state_unchanged(
        paths,
        before,
    )


def test_atomic_generation_result_replace_failure_preserves_original_file(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    (
        _,
        _,
        module,
        reconciler,
        reconciler_error,
    ) = build_reconciler(
        repository
    )

    def fail_replace(
        source,
        target,
    ):
        raise OSError(
            "deterministic Stage 2L os.replace failure"
        )

    monkeypatch.setattr(
        module.os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        reconciler_error,
        match=(
            "(?i)"
            "(atomic|write|replace|persist|generation_result)"
        ),
    ):
        reconciler.reconcile_once(
            TASK_ID
        )

    assert_no_scene_mutation(
        paths,
        before,
    )
    assert_job_records_unchanged(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


@pytest.mark.parametrize(
    "observer",
    [
        "audit",
        "events",
    ],
)
def test_observability_failure_after_atomic_write_does_not_undo_reconciliation(
    tmp_path,
    observer,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    observer_object = (
        FailingAudit(tmp_path)
        if observer == "audit"
        else FailingEvents(tmp_path)
    )

    reconcile(
        repository,
        audit=(
            observer_object
            if observer == "audit"
            else None
        ),
        events=(
            observer_object
            if observer == "events"
            else None
        ),
    )

    document = read_generation(
        tmp_path
    )

    assert matching_task(
        document
    )["status"] == "done"
    assert document["status"] == (
        "completed"
    )
    assert observer_object.calls == 1

    observed_document = (
        observer_object.observed_document
    )
    assert observed_document is not None
    observed_task = matching_task(
        observed_document
    )
    assert observed_task["status"] == "done"
    assert (
        observed_document["status"]
        == "completed"
    )
    assert (
        observed_task["output"]
        == completion_overlay()["asset_file"]
    )

    for key, value in completion_overlay().items():
        assert observed_task["result"][key] == value

    assert_job_records_unchanged(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


def test_stage_2l_does_not_poll_retrieve_materialize_or_access_network(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        paths,
        before,
    ) = prepare_case(tmp_path)

    def forbidden_poll(
        self,
        task_id,
    ):
        raise AssertionError(
            "Stage 2L must not poll provider"
        )

    def forbidden_retrieve(
        self,
        task_id,
    ):
        raise AssertionError(
            "Stage 2L must not retrieve provider result"
        )

    def forbidden_materialize(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Stage 2L must not materialize asset"
        )

    def forbidden_connect(
        self,
        address,
    ):
        raise AssertionError(
            "Stage 2L must not access network"
        )

    monkeypatch.setattr(
        GenerationJobLifecycle,
        "poll_once",
        forbidden_poll,
    )
    monkeypatch.setattr(
        GenerationJobResultLifecycle,
        "retrieve_once",
        forbidden_retrieve,
    )
    monkeypatch.setattr(
        AIResultStorage,
        "save_retrieved_result",
        forbidden_materialize,
    )
    monkeypatch.setattr(
        socket.socket,
        "connect",
        forbidden_connect,
    )

    reconcile(repository)

    assert_job_records_unchanged(
        paths,
        before,
    )
    assert_physical_state_unchanged(
        paths,
        before,
    )


@pytest.mark.parametrize(
    (
        "statuses",
        "expected",
    ),
    [
        (
            [],
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 0,
                "status": "pending",
            },
        ),
        (
            ["done", "done"],
            {
                "generated": 2,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 0,
                "status": "completed",
            },
        ),
        (
            ["submitted"],
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 1,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["running"],
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 1,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["waiting"],
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["processing"],
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["provider_weird_state"],
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["succeeded"],
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["done", "submitted"],
            {
                "generated": 1,
                "failed": 0,
                "cancelled": 0,
                "submitted": 1,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["done", "failed"],
            {
                "generated": 1,
                "failed": 1,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 0,
                "status":
                    "completed_with_errors",
            },
        ),
        (
            ["done", "cancelled"],
            {
                "generated": 1,
                "failed": 0,
                "cancelled": 1,
                "submitted": 0,
                "running": 0,
                "pending": 0,
                "status":
                    "completed_with_errors",
            },
        ),
        (
            ["failed", "submitted"],
            {
                "generated": 0,
                "failed": 1,
                "cancelled": 0,
                "submitted": 1,
                "running": 0,
                "pending": 1,
                "status": "pending",
            },
        ),
        (
            ["failed", "cancelled"],
            {
                "generated": 0,
                "failed": 1,
                "cancelled": 1,
                "submitted": 0,
                "running": 0,
                "pending": 0,
                "status":
                    "completed_with_errors",
            },
        ),
    ],
)
def test_shared_aggregation_helper_preserves_stage_2i_semantics(
    statuses,
    expected,
):
    (
        _,
        aggregate,
        _,
        _,
        _,
    ) = contracts()

    tasks = [
        {
            "task_id":
                f"task-{index}",
            "status":
                status,
        }
        for index, status in enumerate(
            statuses,
            start=1,
        )
    ]
    before_tasks = deepcopy(tasks)

    result = aggregate(tasks)

    assert result == expected
    assert tasks == before_tasks


class VideoAIRouterStub:
    def select(
        self,
        media_type,
        mode="mixed",
        commercial=False,
    ):
        assert media_type == "video"
        assert mode == "free"
        return SimpleNamespace(
            name="Video AI"
        )


class ControlledQueue:
    def __init__(
        self,
        statuses,
    ):
        self.statuses = list(
            statuses
        )
        self.tasks = []

    def add_task(
        self,
        task,
    ):
        self.tasks.append(task)
        return task

    def process_all(self):
        for task, status in zip(
            self.tasks,
            self.statuses,
        ):
            task.status = status
            task.result = {
                "status": status,
            }

        return list(
            self.tasks
        )

    def get_status(self):
        return [
            {
                "task_id": task.task_id,
                "type": task.task_type,
                "status": task.status,
                "metadata": task.metadata,
                "result": task.result,
                "provider":
                    getattr(
                        task.provider,
                        "name",
                        None,
                    ),
                "quality": task.quality,
                "output": task.output,
            }
            for task in self.tasks
        ]


def write_engine_render_plan(
    project_path,
):
    path = (
        Path(project_path)
        / "render"
        / "scene_001"
        / "render_plan.json"
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            {
                "scene_id": 1,
                "render_settings": {
                    "resolution":
                        "3840x2160",
                    "fps": 60,
                    "hdr": True,
                    "color_depth": 10,
                },
                "shots": [
                    {
                        "shot_id": 1,
                        "director_prompt":
                            "shared helper probe",
                        "timeline": {
                            "duration": 1,
                        },
                        "camera": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_generation_engine_uses_shared_aggregation_helper(
    tmp_path,
    monkeypatch,
):
    contracts()

    queue = ControlledQueue(
        ["submitted"]
    )

    monkeypatch.setattr(
        generation_engine_module,
        "GenerationQueue",
        lambda: queue,
    )

    called = {
        "count": 0,
    }

    def fake_aggregate(
        tasks,
    ):
        called["count"] += 1
        assert isinstance(
            tasks,
            list,
        )
        assert len(tasks) == 1

        return {
            "generated": 7,
            "failed": 8,
            "cancelled": 9,
            "submitted": 10,
            "running": 11,
            "pending": 12,
            "status":
                "stage-2l-helper-sentinel",
        }

    assert hasattr(
        generation_engine_module,
        "aggregate_generation_tasks",
    ), (
        "GenerationEngine must import and use "
        "the shared Stage 2L aggregation helper"
    )

    monkeypatch.setattr(
        generation_engine_module,
        "aggregate_generation_tasks",
        fake_aggregate,
    )

    write_engine_render_plan(
        tmp_path
    )

    engine = GenerationEngine(
        project_path=tmp_path,
        quality="4k",
    )
    engine.provider_router = (
        VideoAIRouterStub()
    )

    result_path = Path(
        engine.generate_scene(1)
    )

    output = json.loads(
        result_path.read_text(
            encoding="utf-8"
        )
    )

    assert called["count"] == 1
    assert output["generated"] == 7
    assert output["failed"] == 8
    assert output["cancelled"] == 9
    assert output["submitted"] == 10
    assert output["running"] == 11
    assert output["pending"] == 12
    assert (
        output["status"]
        == "stage-2l-helper-sentinel"
    )


def test_reconciler_uses_same_shared_aggregation_helper(
    tmp_path,
    monkeypatch,
):
    (
        repository,
        _,
        _,
    ) = prepare_case(tmp_path)

    (
        status_module,
        aggregate,
        module,
        reconciler,
        _,
    ) = build_reconciler(
        repository
    )

    assert (
        aggregate
        is status_module.aggregate_generation_tasks
    )

    called = {
        "count": 0,
    }

    def fake_aggregate(
        tasks,
    ):
        called["count"] += 1

        return {
            "generated": 21,
            "failed": 22,
            "cancelled": 23,
            "submitted": 24,
            "running": 25,
            "pending": 26,
            "status":
                "stage-2l-reconciler-helper-sentinel",
        }

    assert hasattr(
        module,
        "aggregate_generation_tasks",
    ), (
        "GenerationResultReconciler must use "
        "the same shared aggregation helper"
    )

    monkeypatch.setattr(
        module,
        "aggregate_generation_tasks",
        fake_aggregate,
    )

    reconciler.reconcile_once(
        TASK_ID
    )

    output = read_generation(
        tmp_path
    )

    assert called["count"] == 1
    assert output["generated"] == 21
    assert output["failed"] == 22
    assert output["cancelled"] == 23
    assert output["submitted"] == 24
    assert output["running"] == 25
    assert output["pending"] == 26
    assert (
        output["status"]
        == "stage-2l-reconciler-helper-sentinel"
    )
