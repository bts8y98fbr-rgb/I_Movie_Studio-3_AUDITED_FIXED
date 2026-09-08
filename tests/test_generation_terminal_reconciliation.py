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
from core.ai_core.generation_job_lifecycle import GenerationJobLifecycle
from core.ai_core.generation_job_repository import GenerationJobRepository
from core.ai_core.generation_job_result_lifecycle import (
    GenerationJobResultLifecycle,
)
from core.ai_core.generation_queue import GenerationTask
from core.ai_core.result_storage import AIResultStorage
from core.movie_engine.generation_result_reconciler import (
    GenerationResultReconciler,
)
from core.movie_engine.generation_status import aggregate_generation_tasks


MODULE_NAME = "core.movie_engine.generation_terminal_reconciler"
TASK_ID = "task-2m-001"
JOB_ID = "job-2m-001"
PROVIDER = "deterministic-remote-video"
TASK_TYPE = "video"
SCENE_ID = 1
SHOT_ID = 2

CANONICAL_RESULT_KEYS = {
    "status",
    "job_id",
    "provider",
    "asset_ready",
}
PROHIBITED_RESULT_KEYS = {
    "result_state",
    "provider_result",
    "asset_id",
    "asset_file",
    "registry_version",
    "error",
    "error_message",
    "reason",
    "provider_error",
}


def contracts():
    try:
        module = importlib.import_module(MODULE_NAME)
    except ModuleNotFoundError as exc:
        if exc.name != MODULE_NAME:
            raise
        pytest.fail(
            "Stage 2M terminal reconciliation module is missing: "
            "expected core.movie_engine.generation_terminal_reconciler",
            pytrace=False,
        )

    reconciler_type = getattr(module, "GenerationTerminalReconciler", None)
    reconciler_error = getattr(
        module,
        "GenerationTerminalReconciliationError",
        None,
    )
    if reconciler_type is None or reconciler_error is None:
        pytest.fail(
            "Stage 2M terminal reconciliation public contract is incomplete",
            pytrace=False,
        )

    return module, reconciler_type, reconciler_error


def build_reconciler(repository, audit=None, events=None):
    module, reconciler_type, reconciler_error = contracts()
    reconciler = reconciler_type(
        job_repository=repository,
        audit=audit,
        events=events,
    )
    assert callable(getattr(reconciler, "reconcile_once", None))
    return module, reconciler, reconciler_error


def terminal_record(status="failed", **overrides):
    record = {
        "format_version": 1,
        "task_id": TASK_ID,
        "task_type": TASK_TYPE,
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "status": status,
        "metadata": {
            "scene_id": SCENE_ID,
            "shot_id": SHOT_ID,
        },
        "terminal_at": "2026-09-08T14:00:00+00:00",
    }
    if status == "succeeded":
        record.update(
            {
                "result_state": "pending_retrieval",
                "asset_ready": False,
            }
        )
    record.update(overrides)
    return record


def canonical_terminal_result(status):
    return {
        "status": status,
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "asset_ready": False,
    }


def task_snapshot(
    *,
    task_id=TASK_ID,
    status="submitted",
    task_type=TASK_TYPE,
    provider=PROVIDER,
    scene_id=SCENE_ID,
    shot_id=SHOT_ID,
    result="default",
    output=None,
):
    if result == "default":
        result = {
            "status": "submitted",
            "job_id": JOB_ID,
            "provider": provider,
            "request_id": "request-preserved",
        }

    return {
        "task_id": task_id,
        "type": task_type,
        "status": status,
        "metadata": {
            "scene_id": scene_id,
            "shot_id": shot_id,
            "future_metadata": {"preserve": True},
        },
        "result": result,
        "provider": provider,
        "quality": "4k",
        "output": output,
        "future_task_field": {"preserve": True},
    }


def generation_result_path(project_path):
    return (
        Path(project_path)
        / "render_output"
        / "scene_001"
        / "generation_result.json"
    )


def write_generation_result(project_path, tasks=None, scene_id=SCENE_ID):
    if tasks is None:
        tasks = [task_snapshot()]
    aggregation = aggregate_generation_tasks(tasks)
    document = {
        "scene_id": scene_id,
        "created": "2026-09-08T13:59:00",
        "quality": "4k",
        "requested_quality": {"resolution": "3840x2160"},
        "actual_quality": {"resolution": "3840x2160"},
        **aggregation,
        "tasks": tasks,
        "future_scene_field": {"preserve": True},
    }
    path = generation_result_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def write_physical_state(project_path):
    root = Path(project_path)
    paths = {
        "asset": root / "assets" / "video" / "preserve.bin",
        "registry": root / "assets" / "registry.json",
        "version": root / "assets" / "versions" / "preserve" / "v001" / "asset.json",
        "render_plan": root / "render" / "scene_001" / "render_plan.json",
    }
    payloads = {
        "asset": b"stage-2m-asset-bytes\n",
        "registry": b'[{"preserve": "registry"}]\n',
        "version": b'{"preserve": "version"}\n',
        "render_plan": b'{"scene_id": 1, "preserve": "render-plan"}\n',
    }
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payloads[name])
    return paths


def create_repository(project_path, terminal_status="failed"):
    repository = GenerationJobRepository(project_path)
    task = GenerationTask(
        task_type=TASK_TYPE,
        prompt="Stage 2M terminal reconciliation",
        provider=SimpleNamespace(name=PROVIDER),
        quality="4k",
        project_path=project_path,
        metadata={"scene_id": SCENE_ID, "shot_id": SHOT_ID},
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
    repository.persist_terminal(terminal_record(terminal_status))
    return repository


def add_retrieved(repository):
    repository.persist_retrieved(
        {
            "format_version": 1,
            "task_id": TASK_ID,
            "task_type": TASK_TYPE,
            "job_id": JOB_ID,
            "provider": PROVIDER,
            "metadata": {"scene_id": SCENE_ID, "shot_id": SHOT_ID},
            "result_state": "retrieved",
            "asset_ready": False,
            "provider_result": {"job_id": JOB_ID, "provider": PROVIDER},
            "retrieved_at": "2026-09-08T14:01:00+00:00",
        }
    )


def add_finalized(repository):
    repository.persist_finalized(
        {
            "format_version": 1,
            "task_id": TASK_ID,
            "task_type": TASK_TYPE,
            "job_id": JOB_ID,
            "provider": PROVIDER,
            "metadata": {"scene_id": SCENE_ID, "shot_id": SHOT_ID},
            "result_state": "finalized",
            "asset_ready": True,
            "asset_id": "contradictory-asset",
            "asset_file": "assets/video/preserve.bin",
            "registry_version": 1,
            "finalized_at": "2026-09-08T14:02:00+00:00",
        }
    )


def capture(paths):
    return {
        name: path.read_bytes()
        for name, path in paths.items()
        if path.exists()
    }


def prepare_case(
    project_path,
    *,
    terminal_status="failed",
    tasks=None,
    scene_id=SCENE_ID,
):
    repository = create_repository(project_path, terminal_status)
    physical = write_physical_state(project_path)
    generation = write_generation_result(project_path, tasks, scene_id)
    paths = {
        "submitted": repository.receipt_path(TASK_ID),
        "terminal": repository.terminal_path(TASK_ID),
        "generation_result": generation,
        **physical,
    }
    return {
        "repository": repository,
        "paths": paths,
        "before": capture(paths),
    }


def refresh_before(case):
    case["before"] = capture(case["paths"])


def assert_unchanged(case, include_scene=True):
    for name, original in case["before"].items():
        if not include_scene and name == "generation_result":
            continue
        assert case["paths"][name].read_bytes() == original


def read_generation(project_path):
    return json.loads(
        generation_result_path(project_path).read_text(encoding="utf-8")
    )


def matching_task(document):
    matches = [
        task
        for task in document["tasks"]
        if isinstance(task, dict) and task.get("task_id") == TASK_ID
    ]
    assert len(matches) == 1
    return matches[0]


def rewrite_json(path, transform):
    value = json.loads(path.read_text(encoding="utf-8"))
    transform(value)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def reconcile(case, audit=None, events=None, task_id=TASK_ID):
    _, reconciler, _ = build_reconciler(
        case["repository"],
        audit=audit,
        events=events,
    )
    return reconciler.reconcile_once(task_id)


def expect_reconciliation_error(case, match="error|invalid|mismatch|contradict"):
    _, reconciler, error = build_reconciler(case["repository"])
    with pytest.raises(error, match=f"(?i)({match})"):
        reconciler.reconcile_once(TASK_ID)


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
@pytest.mark.parametrize(
    "local_status",
    ["waiting", "processing", "submitted", "running", "succeeded"],
)
def test_allowed_local_pre_states_reconcile_to_durable_terminal(
    tmp_path,
    terminal_status,
    local_status,
):
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task_snapshot(status=local_status)],
    )
    reconcile(case)
    document = read_generation(tmp_path)
    task = matching_task(document)
    assert task["status"] == terminal_status
    assert task["output"] is None
    assert task["result"]["status"] == terminal_status
    assert task["result"]["job_id"] == JOB_ID
    assert task["result"]["provider"] == PROVIDER
    assert task["result"]["asset_ready"] is False
    assert document["status"] == "completed_with_errors"
    assert_unchanged(case, include_scene=False)


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_none_result_becomes_exact_canonical_terminal_dictionary(
    tmp_path,
    terminal_status,
):
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task_snapshot(result=None)],
    )
    reconcile(case)
    result = matching_task(read_generation(tmp_path))["result"]
    assert result == canonical_terminal_result(terminal_status)
    assert set(result) == CANONICAL_RESULT_KEYS
    assert not (set(result) & PROHIBITED_RESULT_KEYS)
    assert_unchanged(case, include_scene=False)


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_safe_result_fields_survive_without_fabricated_terminal_details(
    tmp_path,
    terminal_status,
):
    safe = {
        "status": "submitted",
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "request_id": "request-preserved",
        "latency_ms": 123,
        "future_field": {"preserve": True},
    }
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task_snapshot(result=safe)],
    )
    reconcile(case)
    result = matching_task(read_generation(tmp_path))["result"]
    for key in ("request_id", "latency_ms", "future_field"):
        assert result[key] == safe[key]
    for key, value in canonical_terminal_result(terminal_status).items():
        assert result[key] == value
    assert not (set(result) & PROHIBITED_RESULT_KEYS)
    assert_unchanged(case, include_scene=False)


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_result_without_status_is_valid_pre_terminal_input(
    tmp_path,
    terminal_status,
):
    result = {
        "job_id": JOB_ID,
        "provider": PROVIDER,
        "request_id": "status-absent-but-safe",
    }
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task_snapshot(result=result)],
    )
    reconcile(case)
    reconciled = matching_task(read_generation(tmp_path))["result"]
    assert reconciled["request_id"] == "status-absent-but-safe"
    for key, value in canonical_terminal_result(terminal_status).items():
        assert reconciled[key] == value
    assert not (set(reconciled) & PROHIBITED_RESULT_KEYS)
    assert_unchanged(case, include_scene=False)


@pytest.mark.parametrize("source", ["submitted", "terminal"])
def test_requested_task_id_mismatch_is_rejected_before_scene_mutation(
    tmp_path,
    source,
):
    case = prepare_case(tmp_path)
    rewrite_json(
        case["paths"][source],
        lambda record: record.update(task_id="embedded-other-task"),
    )
    refresh_before(case)
    expect_reconciliation_error(case, "task|identity|mismatch")
    assert_unchanged(case)


@pytest.mark.parametrize("field", ["task_type", "job_id", "provider"])
def test_submitted_terminal_cross_record_identity_mismatch_is_rejected(
    tmp_path,
    field,
):
    case = prepare_case(tmp_path)
    rewrite_json(
        case["paths"]["terminal"],
        lambda record: record.update({field: f"wrong-{field}"}),
    )
    refresh_before(case)
    expect_reconciliation_error(case, "identity|mismatch|task|job|provider")
    assert_unchanged(case)


@pytest.mark.parametrize("field", ["scene_id", "shot_id"])
def test_submitted_terminal_metadata_identity_mismatch_is_rejected(
    tmp_path,
    field,
):
    case = prepare_case(tmp_path)
    rewrite_json(
        case["paths"]["terminal"],
        lambda record: record["metadata"].update({field: 999}),
    )
    refresh_before(case)
    expect_reconciliation_error(case, "metadata|identity|mismatch|scene|shot")
    assert_unchanged(case)


@pytest.mark.parametrize("contradiction", ["retrieved", "finalized", "both"])
def test_later_durable_chain_contradictions_are_rejected_without_repair(
    tmp_path,
    contradiction,
):
    case = prepare_case(tmp_path)
    if contradiction in {"retrieved", "both"}:
        add_retrieved(case["repository"])
        case["paths"]["retrieved"] = case["repository"].retrieved_path(TASK_ID)
    if contradiction in {"finalized", "both"}:
        add_finalized(case["repository"])
        case["paths"]["finalized"] = case["repository"].finalized_path(TASK_ID)
    refresh_before(case)
    expect_reconciliation_error(
        case,
        "retrieved|finalized|chain|contradict",
    )
    assert_unchanged(case)


@pytest.mark.parametrize("missing", ["submitted", "terminal"])
def test_missing_durable_source_record_is_public_reconciliation_error(
    tmp_path,
    missing,
):
    case = prepare_case(tmp_path)
    case["paths"][missing].unlink()
    case["paths"].pop(missing)
    refresh_before(case)
    expect_reconciliation_error(case, "missing|submitted|terminal|record")
    assert_unchanged(case)


@pytest.mark.parametrize("source", ["submitted", "terminal"])
@pytest.mark.parametrize("malformed", [b"{not-json", b'{"format_version": 1}\n'])
def test_malformed_durable_source_record_is_public_reconciliation_error(
    tmp_path,
    source,
    malformed,
):
    case = prepare_case(tmp_path)
    case["paths"][source].write_bytes(malformed)
    refresh_before(case)
    expect_reconciliation_error(
        case,
        "invalid|corrupt|schema|field|submitted|terminal|record",
    )
    assert_unchanged(case)


def test_succeeded_terminal_is_rejected_without_success_reconciler_crossover(
    tmp_path,
    monkeypatch,
):
    case = prepare_case(tmp_path)
    case["repository"].persist_terminal(terminal_record("succeeded"))
    refresh_before(case)
    monkeypatch.setattr(
        GenerationResultReconciler,
        "reconcile_once",
        lambda *args, **kwargs: pytest.fail(
            "Stage 2M must not delegate succeeded terminal to Stage 2L"
        ),
    )
    expect_reconciliation_error(case, "succeeded|terminal|eligible|status")
    assert_unchanged(case)


@pytest.mark.parametrize("scene_id", [None, True, "../escape"])
def test_invalid_or_unsafe_durable_scene_identity_is_rejected(
    tmp_path,
    scene_id,
):
    case = prepare_case(tmp_path)
    for source in ("submitted", "terminal"):
        rewrite_json(
            case["paths"][source],
            lambda record: record["metadata"].update(scene_id=scene_id),
        )
    refresh_before(case)
    expect_reconciliation_error(case, "scene|identity|invalid|unsafe")
    assert_unchanged(case)


@pytest.mark.parametrize("problem", ["missing", "invalid-json", "non-dict"])
def test_generation_result_document_must_exist_and_be_valid_dictionary(
    tmp_path,
    problem,
):
    case = prepare_case(tmp_path)
    path = case["paths"]["generation_result"]
    if problem == "missing":
        path.unlink()
        case["paths"].pop("generation_result")
    elif problem == "invalid-json":
        path.write_bytes(b"{broken-json")
    else:
        path.write_bytes(b"[]\n")
    refresh_before(case)
    expect_reconciliation_error(
        case,
        "generation_result|scene|missing|invalid|document|json",
    )
    assert_unchanged(case)


def test_generation_result_scene_identity_cannot_override_durable_identity(tmp_path):
    case = prepare_case(tmp_path, scene_id=999)
    expect_reconciliation_error(case, "scene|identity|mismatch")
    assert_unchanged(case)


@pytest.mark.parametrize("problem", ["non-list", "no-match", "duplicate"])
def test_generation_result_task_collection_and_cardinality_are_strict(
    tmp_path,
    problem,
):
    if problem == "non-list":
        tasks = {"not": "a-list"}
    elif problem == "no-match":
        tasks = [task_snapshot(task_id="other-task")]
    else:
        tasks = [task_snapshot(), task_snapshot()]
    case = prepare_case(tmp_path, tasks=tasks)
    expect_reconciliation_error(
        case,
        "task|collection|list|cardinality|missing|duplicate",
    )
    assert_unchanged(case)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "image"),
        ("provider", "wrong-provider"),
        ("scene_id", 999),
        ("shot_id", 999),
    ],
)
def test_local_task_identity_must_match_durable_terminal(
    tmp_path,
    field,
    value,
):
    task = task_snapshot()
    if field in {"scene_id", "shot_id"}:
        task["metadata"][field] = value
    else:
        task[field] = value
    case = prepare_case(tmp_path, tasks=[task])
    expect_reconciliation_error(
        case,
        "task|identity|mismatch|provider|scene|shot|type",
    )
    assert_unchanged(case)


def test_local_task_metadata_must_be_dictionary(tmp_path):
    task = task_snapshot()
    task["metadata"] = "not-a-dictionary"
    case = prepare_case(tmp_path, tasks=[task])
    expect_reconciliation_error(case, "metadata|dict|invalid")
    assert_unchanged(case)


@pytest.mark.parametrize(
    "malformed_result",
    ["not-a-dict", ["bad"], 123, 1.5, True],
)
def test_non_dictionary_non_none_task_result_is_rejected_atomically(
    tmp_path,
    malformed_result,
):
    case = prepare_case(
        tmp_path,
        tasks=[task_snapshot(result=malformed_result)],
    )
    expect_reconciliation_error(case, "result|dict|shape|invalid")
    assert_unchanged(case)


@pytest.mark.parametrize("field", ["job_id", "provider"])
def test_existing_result_identity_must_match_durable_terminal(tmp_path, field):
    result = {
        "status": "submitted",
        "job_id": JOB_ID,
        "provider": PROVIDER,
    }
    result[field] = f"wrong-{field}"
    case = prepare_case(tmp_path, tasks=[task_snapshot(result=result)])
    expect_reconciliation_error(case, "result|identity|job|provider|mismatch")
    assert_unchanged(case)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("asset_ready", True),
        ("result_state", "finalized"),
        ("asset_id", "local-asset"),
        ("asset_file", "assets/video/local.bin"),
        ("registry_version", 1),
        ("provider_result", {"opaque": True}),
    ],
)
def test_existing_success_or_asset_state_blocks_terminal_reconciliation(
    tmp_path,
    field,
    value,
):
    result = {
        "status": "submitted",
        "job_id": JOB_ID,
        "provider": PROVIDER,
        field: value,
    }
    case = prepare_case(tmp_path, tasks=[task_snapshot(result=result)])
    expect_reconciliation_error(
        case,
        "result|asset|success|finalized|provider|contradict",
    )
    assert_unchanged(case)


@pytest.mark.parametrize(
    ("task_status", "result_status"),
    [
        ("submitted", "done"),
        ("running", "failed"),
        ("submitted", "cancelled"),
        ("processing", "unknown-terminal-like-state"),
    ],
)
def test_contradictory_existing_result_status_is_rejected(
    tmp_path,
    task_status,
    result_status,
):
    result = {
        "status": result_status,
        "job_id": JOB_ID,
        "provider": PROVIDER,
    }
    case = prepare_case(
        tmp_path,
        tasks=[task_snapshot(status=task_status, result=result)],
    )
    expect_reconciliation_error(case, "result|status|contradict|unknown")
    assert_unchanged(case)


@pytest.mark.parametrize(
    ("terminal_status", "local_status"),
    [
        ("failed", "done"),
        ("cancelled", "done"),
        ("failed", "cancelled"),
        ("cancelled", "failed"),
        ("failed", "unknown-local-state"),
    ],
)
def test_done_opposite_or_unknown_local_status_is_rejected(
    tmp_path,
    terminal_status,
    local_status,
):
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task_snapshot(status=local_status)],
    )
    expect_reconciliation_error(
        case,
        "status|done|opposite|unknown|contradict|terminal",
    )
    assert_unchanged(case)


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_nonempty_local_output_is_terminal_contradiction(
    tmp_path,
    terminal_status,
):
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task_snapshot(output="assets/video/unexpected.bin")],
    )
    expect_reconciliation_error(case, "output|asset|contradict")
    assert_unchanged(case)


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_same_terminal_canonical_state_is_byte_idempotent(
    tmp_path,
    terminal_status,
):
    task = task_snapshot(
        status=terminal_status,
        result=canonical_terminal_result(terminal_status),
    )
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task],
    )
    reconcile(case)
    assert_unchanged(case)
    reconcile(case)
    assert_unchanged(case)


@pytest.mark.parametrize(
    ("conflict", "value"),
    [
        ("result_status", "submitted"),
        ("job_id", "wrong-job"),
        ("provider", "wrong-provider"),
        ("asset_ready", True),
        ("output", "assets/video/unexpected.bin"),
        ("asset_id", "unexpected-asset"),
    ],
)
def test_same_terminal_inconsistent_overlay_is_rejected(
    tmp_path,
    conflict,
    value,
):
    result = canonical_terminal_result("failed")
    output = None
    if conflict == "result_status":
        result["status"] = value
    elif conflict == "output":
        output = value
    else:
        result[conflict] = value
    case = prepare_case(
        tmp_path,
        tasks=[task_snapshot(status="failed", result=result, output=output)],
    )
    expect_reconciliation_error(
        case,
        "terminal|canonical|result|identity|asset|output|contradict",
    )
    assert_unchanged(case)


@pytest.mark.parametrize(
    ("terminal_status", "other_statuses", "expected"),
    [
        ("failed", [], {"generated": 0, "failed": 1, "cancelled": 0, "submitted": 0, "running": 0, "pending": 0, "status": "completed_with_errors"}),
        ("cancelled", [], {"generated": 0, "failed": 0, "cancelled": 1, "submitted": 0, "running": 0, "pending": 0, "status": "completed_with_errors"}),
        ("failed", ["submitted"], {"generated": 0, "failed": 1, "cancelled": 0, "submitted": 1, "running": 0, "pending": 1, "status": "pending"}),
        ("cancelled", ["running"], {"generated": 0, "failed": 0, "cancelled": 1, "submitted": 0, "running": 1, "pending": 1, "status": "pending"}),
        ("failed", ["done"], {"generated": 1, "failed": 1, "cancelled": 0, "submitted": 0, "running": 0, "pending": 0, "status": "completed_with_errors"}),
        ("cancelled", ["done"], {"generated": 1, "failed": 0, "cancelled": 1, "submitted": 0, "running": 0, "pending": 0, "status": "completed_with_errors"}),
        ("failed", ["cancelled"], {"generated": 0, "failed": 1, "cancelled": 1, "submitted": 0, "running": 0, "pending": 0, "status": "completed_with_errors"}),
    ],
)
def test_complete_scene_is_reaggregated_with_shared_stage_2i_semantics(
    tmp_path,
    terminal_status,
    other_statuses,
    expected,
):
    other_tasks = [
        task_snapshot(
            task_id=f"other-{index}",
            status=status,
            provider="other-provider",
            result={"status": status},
        )
        for index, status in enumerate(other_statuses, start=1)
    ]
    case = prepare_case(
        tmp_path,
        terminal_status=terminal_status,
        tasks=[task_snapshot(), *other_tasks],
    )
    reconcile(case)
    document = read_generation(tmp_path)
    for field, value in expected.items():
        assert document[field] == value
    assert document["future_scene_field"] == {"preserve": True}
    assert document["tasks"][1:] == other_tasks
    assert_unchanged(case, include_scene=False)


def test_reconciler_uses_module_level_shared_aggregation_helper(
    tmp_path,
    monkeypatch,
):
    case = prepare_case(tmp_path)
    module, reconciler, _ = build_reconciler(case["repository"])
    assert hasattr(module, "aggregate_generation_tasks")
    called = {"count": 0, "tasks": None}
    expected = {
        "generated": 11,
        "failed": 12,
        "cancelled": 13,
        "submitted": 14,
        "running": 15,
        "pending": 16,
        "status": "stage-2m-helper-sentinel",
    }

    def fake_aggregate(tasks):
        called["count"] += 1
        called["tasks"] = tasks
        return dict(expected)

    monkeypatch.setattr(module, "aggregate_generation_tasks", fake_aggregate)
    reconciler.reconcile_once(TASK_ID)
    document = read_generation(tmp_path)
    assert called["count"] == 1
    assert isinstance(called["tasks"], list)
    for field, value in expected.items():
        assert document[field] == value
    assert called["count"] == 1


def test_atomic_replace_failure_preserves_scene_and_all_sources(
    tmp_path,
    monkeypatch,
):
    case = prepare_case(tmp_path)
    module, reconciler, error = build_reconciler(case["repository"])

    def fail_replace(source, target):
        raise OSError("deterministic Stage 2M replace failure")

    monkeypatch.setattr(module.os, "replace", fail_replace)
    with pytest.raises(error, match="(?i)(atomic|replace|write|persist)"):
        reconciler.reconcile_once(TASK_ID)
    assert_unchanged(case)


class FailingObserver:
    def __init__(self, project_path, terminal_status, method):
        self.project_path = Path(project_path)
        self.terminal_status = terminal_status
        self.method = method
        self.calls = 0

    def _observe(self):
        self.calls += 1
        document = read_generation(self.project_path)
        task = matching_task(document)
        assert task["status"] == self.terminal_status
        assert task["result"] == canonical_terminal_result(self.terminal_status)
        assert document["status"] == "completed_with_errors"
        raise OSError("deterministic Stage 2M observer failure")

    def record(self, event, data):
        assert self.method == "audit"
        self._observe()

    def emit(self, event, data):
        assert self.method == "events"
        self._observe()


@pytest.mark.parametrize("observer_kind", ["audit", "events"])
def test_observability_runs_once_after_durable_scene_write_and_is_nonfatal(
    tmp_path,
    observer_kind,
):
    case = prepare_case(
        tmp_path,
        tasks=[task_snapshot(result=None)],
    )
    observer = FailingObserver(tmp_path, "failed", observer_kind)
    reconcile(
        case,
        audit=observer if observer_kind == "audit" else None,
        events=observer if observer_kind == "events" else None,
    )
    assert observer.calls == 1
    assert matching_task(read_generation(tmp_path))["status"] == "failed"
    assert_unchanged(case, include_scene=False)


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_successful_reconciliation_preserves_durable_and_physical_bytes(
    tmp_path,
    terminal_status,
):
    case = prepare_case(tmp_path, terminal_status=terminal_status)
    reconcile(case)
    assert_unchanged(case, include_scene=False)


def test_unrelated_scene_and_task_fields_are_preserved(tmp_path):
    other = task_snapshot(
        task_id="unrelated-task",
        status="running",
        provider="other-provider",
        result={"status": "running", "future": {"nested": True}},
    )
    original_other = deepcopy(other)
    case = prepare_case(tmp_path, tasks=[task_snapshot(), other])
    before_document = read_generation(tmp_path)
    reconcile(case)
    after = read_generation(tmp_path)
    assert after["tasks"][1] == original_other
    for field in (
        "scene_id",
        "created",
        "quality",
        "requested_quality",
        "actual_quality",
        "future_scene_field",
    ):
        assert after[field] == before_document[field]
    assert_unchanged(case, include_scene=False)


def test_stage_2m_never_calls_other_lifecycles_assets_providers_or_network(
    tmp_path,
    monkeypatch,
):
    case = prepare_case(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Stage 2M forbidden call")

    monkeypatch.setattr(GenerationJobLifecycle, "poll_once", forbidden)
    monkeypatch.setattr(GenerationJobResultLifecycle, "retrieve_once", forbidden)
    monkeypatch.setattr(GenerationJobAssetLifecycle, "finalize_once", forbidden)
    monkeypatch.setattr(GenerationResultReconciler, "reconcile_once", forbidden)
    monkeypatch.setattr(AIResultStorage, "save_retrieved_result", forbidden)
    monkeypatch.setattr(
        AssetRegistry,
        "ensure_retrieved_registration",
        forbidden,
    )
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(case["repository"], "persist", forbidden)
    monkeypatch.setattr(case["repository"], "persist_terminal", forbidden)
    monkeypatch.setattr(case["repository"], "persist_retrieved", forbidden)
    monkeypatch.setattr(case["repository"], "persist_finalized", forbidden)
    reconcile(case)
    assert_unchanged(case, include_scene=False)
