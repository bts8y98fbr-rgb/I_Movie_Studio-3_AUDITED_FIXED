from copy import deepcopy
import ast
import importlib
import inspect
import json

import pytest

from core.ai_core.generation_job_repository import (
    GenerationJobReceiptError,
    GenerationJobRepositoryError,
    GenerationJobTerminalError,
)
from core.movie_engine.generation_lifecycle_coordinator import (
    GenerationLifecycleCoordinatorError,
)


FUTURE_MODULE = "core.movie_engine.generation_scene_lifecycle"
SCENE_ID = 1
ACTIVE_STATUSES = (
    "waiting",
    "processing",
    "submitted",
    "running",
    "succeeded",
)
TERMINAL_LOCAL_STATUSES = (
    "done",
    "failed",
    "cancelled",
)
VALID_TOPOLOGIES = (
    (None, False, False, "poll"),
    ("failed", False, False, "reconcile_terminal"),
    ("cancelled", False, False, "reconcile_terminal"),
    ("succeeded", False, False, "retrieve"),
    ("succeeded", True, False, "finalize"),
    ("succeeded", True, True, "reconcile_success"),
)
INVALID_TOPOLOGIES = (
    (None, True, False),
    (None, False, True),
    (None, True, True),
    ("failed", True, False),
    ("failed", False, True),
    ("failed", True, True),
    ("cancelled", True, False),
    ("cancelled", False, True),
    ("cancelled", True, True),
    ("succeeded", False, True),
)


def _load_future_module():
    return importlib.import_module(FUTURE_MODULE)


def _task(
    task_id="task-001",
    *,
    status="submitted",
    task_type="video",
    provider="deterministic-video",
    scene_id=SCENE_ID,
    shot_id=1,
    result=None,
):
    return {
        "task_id": task_id,
        "type": task_type,
        "provider": provider,
        "status": status,
        "metadata": {
            "scene_id": scene_id,
            "shot_id": shot_id,
        },
        "result": deepcopy(result),
        "output": None,
        "quality": "4k",
    }


def _receipt(task):
    return {
        "format_version": 1,
        "task_id": task["task_id"],
        "task_type": task["type"],
        "status": "submitted",
        "job_id": f"job-{task['task_id']}",
        "provider": task["provider"],
        "metadata": deepcopy(task["metadata"]),
        "submitted_at": "2026-09-08T00:00:00+00:00",
    }


def _terminal(receipt, status="succeeded"):
    record = {
        "format_version": 1,
        "task_id": receipt["task_id"],
        "task_type": receipt["task_type"],
        "job_id": receipt["job_id"],
        "provider": receipt["provider"],
        "status": status,
        "metadata": deepcopy(receipt["metadata"]),
        "terminal_at": "2026-09-08T00:01:00+00:00",
    }
    if status == "succeeded":
        record.update(
            {
                "result_state": "pending_retrieval",
                "asset_ready": False,
            }
        )
    return record


def _scene(tasks, scene_id=SCENE_ID):
    return {
        "scene_id": scene_id,
        "tasks": deepcopy(tasks),
        "status": "pending",
        "created": "2026-09-08T00:00:00+00:00",
    }


def _scene_path(project_path, scene_id=SCENE_ID):
    return (
        project_path
        / "render_output"
        / f"scene_{scene_id:03d}"
        / "generation_result.json"
    )


def _write_scene(project_path, document, scene_id=SCENE_ID):
    path = _scene_path(project_path, scene_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2),
        encoding="utf-8",
    )
    return path


class FakeRepository:
    def __init__(
        self,
        tasks=(),
        *,
        trace=None,
    ):
        self.receipts = {
            task["task_id"]: _receipt(task)
            for task in tasks
            if isinstance(task, dict)
            and isinstance(task.get("task_id"), str)
            and task.get("task_id")
            and isinstance(task.get("metadata"), dict)
            and isinstance(task.get("type"), str)
            and isinstance(task.get("provider"), str)
        }
        self.terminals = {}
        self.retrieved = set()
        self.finalized = set()
        self.effects = {}
        self.calls = []
        self.trace = trace if trace is not None else []

    def set_topology(
        self,
        task_id,
        *,
        terminal_status=None,
        retrieved=False,
        finalized=False,
    ):
        task_id = str(task_id)
        if terminal_status is None:
            self.terminals.pop(task_id, None)
        else:
            self.terminals[task_id] = _terminal(
                self.receipts[task_id],
                terminal_status,
            )
        if retrieved:
            self.retrieved.add(task_id)
        else:
            self.retrieved.discard(task_id)
        if finalized:
            self.finalized.add(task_id)
        else:
            self.finalized.discard(task_id)

    def _value(self, name, task_id, default):
        task_id = str(task_id)
        self.calls.append((name, task_id))
        self.trace.append(("repository", name, task_id))
        effect = self.effects.get((name, task_id), self.effects.get(name))
        if isinstance(effect, BaseException):
            raise effect
        if callable(effect):
            return effect(task_id)
        return deepcopy(default)

    def resume(self, task_id):
        task_id = str(task_id)
        if ("resume", task_id) in self.effects or "resume" in self.effects:
            return self._value("resume", task_id, None)
        if task_id not in self.receipts:
            original = GenerationJobRepositoryError(
                f"missing submitted receipt for {task_id}"
            )
            self.calls.append(("resume", task_id))
            self.trace.append(("repository", "resume", task_id))
            raise original
        return self._value("resume", task_id, self.receipts[task_id])

    def terminal_exists(self, task_id):
        task_id = str(task_id)
        return self._value(
            "terminal_exists",
            task_id,
            task_id in self.terminals,
        )

    def load_terminal(self, task_id):
        task_id = str(task_id)
        return self._value(
            "load_terminal",
            task_id,
            self.terminals.get(task_id),
        )

    def retrieved_exists(self, task_id):
        task_id = str(task_id)
        return self._value(
            "retrieved_exists",
            task_id,
            task_id in self.retrieved,
        )

    def finalized_exists(self, task_id):
        task_id = str(task_id)
        return self._value(
            "finalized_exists",
            task_id,
            task_id in self.finalized,
        )

    def load_retrieved(self, task_id):
        raise AssertionError(
            "Stage 2O must not load retrieved payloads directly"
        )

    def load_finalized(self, task_id):
        raise AssertionError(
            "Stage 2O must not load finalized payloads directly"
        )

    def persist(self, *args, **kwargs):
        raise AssertionError("Stage 2O must not persist submitted state")

    def persist_terminal(self, *args, **kwargs):
        raise AssertionError("Stage 2O must not persist terminal state")

    def persist_retrieved(self, *args, **kwargs):
        raise AssertionError("Stage 2O must not persist retrieved state")

    def persist_finalized(self, *args, **kwargs):
        raise AssertionError("Stage 2O must not persist finalized state")


class ResolverBomb:
    def __init__(self):
        self.calls = 0

    def get(self, name):
        self.calls += 1
        raise AssertionError("Stage 2O must not resolve providers directly")


class ObserverBomb:
    def __init__(self):
        self.calls = 0

    def record(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Stage 2O must not record audit directly")

    def emit(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Stage 2O must not emit events directly")


class CoordinatorControl:
    def __init__(self, *, trace=None):
        self.initializations = []
        self.calls = []
        self.results = {}
        self.effects = {}
        self.trace = trace if trace is not None else []


def _coordinator_class(control):
    class CoordinatorSpy:
        def __init__(self, *args, **kwargs):
            control.initializations.append((args, kwargs))
            control.trace.append(("coordinator", "init", None))

        def advance_once(self, task_id):
            task_id = str(task_id)
            control.calls.append(task_id)
            control.trace.append(("coordinator", "advance_once", task_id))
            effect = control.effects.get(task_id)
            if isinstance(effect, BaseException):
                raise effect
            if callable(effect):
                return effect(task_id)
            return control.results.setdefault(
                task_id,
                {
                    "task_id": task_id,
                    "action": "poll",
                    "result": {"child": task_id},
                },
            )

    return CoordinatorSpy


def _install_coordinator(monkeypatch, module, control=None):
    control = control or CoordinatorControl()
    monkeypatch.setattr(
        module,
        "GenerationLifecycleCoordinator",
        _coordinator_class(control),
    )
    return control


def _argument(initialization, name, position):
    args, kwargs = initialization
    if name in kwargs:
        return kwargs[name]
    if len(args) > position:
        return args[position]
    return None


def _make_lifecycle(
    module,
    project_path,
    repository,
    resolver,
    audit,
    events,
    *,
    include_repository=True,
    include_observers=True,
):
    kwargs = {}
    if include_repository:
        kwargs["job_repository"] = repository
    if include_observers:
        kwargs.update(audit=audit, events=events)
    return module.GenerationSceneLifecycle(
        project_path,
        resolver,
        **kwargs,
    )


def _assert_exact_dependencies(
    initialization,
    repository,
    resolver,
    audit,
    events,
):
    assert _argument(initialization, "job_repository", 0) is repository
    assert _argument(initialization, "provider_resolver", 1) is resolver
    assert _argument(initialization, "audit", 2) is audit
    assert _argument(initialization, "events", 3) is events


def _valid_single_task_setup(
    monkeypatch,
    tmp_path,
    *,
    local_status="submitted",
    terminal_status=None,
    retrieved=False,
    finalized=False,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task(status=local_status)
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    repository.set_topology(
        task["task_id"],
        terminal_status=terminal_status,
        retrieved=retrieved,
        finalized=finalized,
    )
    resolver = ResolverBomb()
    audit = ObserverBomb()
    events = ObserverBomb()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        resolver,
        audit,
        events,
    )
    return (
        module,
        control,
        task,
        repository,
        resolver,
        audit,
        events,
        lifecycle,
    )


@pytest.mark.parametrize("status", ACTIVE_STATUSES)
def test_every_active_local_status_is_eligible(
    monkeypatch,
    tmp_path,
    status,
):
    (
        _,
        control,
        task,
        repository,
        resolver,
        audit,
        events,
        lifecycle,
    ) = _valid_single_task_setup(
        monkeypatch,
        tmp_path,
        local_status=status,
    )
    child_result = control.results.setdefault(
        task["task_id"],
        {"task_id": task["task_id"], "action": "poll", "result": object()},
    )

    returned = lifecycle.advance_once(SCENE_ID)

    assert set(returned) == {"scene_id", "advanced", "advanced_count"}
    assert returned["scene_id"] == SCENE_ID
    assert returned["advanced"] == [child_result]
    assert returned["advanced"][0] is child_result
    assert returned["advanced_count"] == 1
    assert control.calls == [task["task_id"]]
    assert len(control.initializations) == 1
    _assert_exact_dependencies(
        control.initializations[0],
        repository,
        resolver,
        audit,
        events,
    )
    assert resolver.calls == audit.calls == events.calls == 0


@pytest.mark.parametrize(
    "terminal_status,retrieved,finalized,planned_action",
    VALID_TOPOLOGIES,
)
def test_every_valid_durable_topology_passes_complete_preflight(
    monkeypatch,
    tmp_path,
    terminal_status,
    retrieved,
    finalized,
    planned_action,
):
    (
        _,
        control,
        task,
        _,
        _,
        _,
        _,
        lifecycle,
    ) = _valid_single_task_setup(
        monkeypatch,
        tmp_path,
        terminal_status=terminal_status,
        retrieved=retrieved,
        finalized=finalized,
    )
    stage_2n_result = {
        "task_id": task["task_id"],
        "action": planned_action,
        "result": {"topology": planned_action},
    }
    control.results[task["task_id"]] = stage_2n_result

    returned = lifecycle.advance_once(SCENE_ID)

    assert returned["advanced"] == [stage_2n_result]
    assert returned["advanced"][0] is stage_2n_result
    assert control.calls == [task["task_id"]]


@pytest.mark.parametrize(
    "terminal_status,retrieved,finalized",
    INVALID_TOPOLOGIES,
)
def test_invalid_topology_rejects_whole_scene_before_dispatch(
    monkeypatch,
    tmp_path,
    terminal_status,
    retrieved,
    finalized,
):
    (
        module,
        control,
        _,
        _,
        resolver,
        audit,
        events,
        lifecycle,
    ) = _valid_single_task_setup(
        monkeypatch,
        tmp_path,
        terminal_status=terminal_status,
        retrieved=retrieved,
        finalized=finalized,
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert control.initializations == []
    assert control.calls == []
    assert resolver.calls == audit.calls == events.calls == 0


@pytest.mark.parametrize(
    "scene_id",
    (True, False, 0, -1, 1.5, "1", None),
)
def test_invalid_requested_scene_identity_rejects_before_io_or_dispatch(
    monkeypatch,
    tmp_path,
    scene_id,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(scene_id)

    assert repository.calls == []
    assert control.initializations == []
    assert control.calls == []


def test_missing_scene_document_rejects_before_dispatch(monkeypatch, tmp_path):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


@pytest.mark.parametrize(
    "raw",
    (
        b"\xff\xfe",
        b"{not-json",
        b"[]",
        b"null",
    ),
    ids=("invalid-utf8", "invalid-json", "list-root", "null-root"),
)
def test_malformed_scene_document_rejects_before_dispatch(
    monkeypatch,
    tmp_path,
    raw,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    path = _scene_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


def test_unreadable_scene_path_rejects_before_dispatch(monkeypatch, tmp_path):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    path = _scene_path(tmp_path)
    path.mkdir(parents=True)
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


@pytest.mark.parametrize(
    "document",
    (
        {"scene_id": 2, "tasks": []},
        {"scene_id": 1},
        {"scene_id": 1, "tasks": None},
        {"scene_id": 1, "tasks": {}},
        {"scene_id": 1, "tasks": ["task"]},
        {"scene_id": 1, "tasks": [1]},
    ),
    ids=(
        "scene-mismatch",
        "tasks-missing",
        "tasks-none",
        "tasks-dict",
        "task-string",
        "task-number",
    ),
)
def test_invalid_scene_structure_rejects_before_repository_or_dispatch(
    monkeypatch,
    tmp_path,
    document,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    _write_scene(tmp_path, document)
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


@pytest.mark.parametrize(
    "field,value",
    (
        ("task_id", None),
        ("task_id", ""),
        ("task_id", 7),
        ("type", None),
        ("type", ""),
        ("provider", None),
        ("provider", ""),
        ("metadata", None),
        ("metadata", []),
    ),
)
def test_invalid_active_task_structure_blocks_complete_scene(
    monkeypatch,
    tmp_path,
    field,
    value,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    task[field] = value
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


@pytest.mark.parametrize(
    "metadata",
    (
        {"scene_id": None, "shot_id": 1},
        {"scene_id": 2, "shot_id": 1},
        {"scene_id": 1},
        {"scene_id": 1, "shot_id": None},
    ),
)
def test_invalid_active_task_metadata_blocks_complete_scene(
    monkeypatch,
    tmp_path,
    metadata,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    task["metadata"] = metadata
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


def test_duplicate_task_ids_block_before_any_durable_lookup(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    first = _task("duplicate", shot_id=1)
    second = _task("duplicate", shot_id=2)
    _write_scene(tmp_path, _scene([first, second]))
    repository = FakeRepository([first])
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


def test_unknown_local_status_blocks_before_durable_lookup_or_dispatch(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task(status="mystery")
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.calls == []


@pytest.mark.parametrize("result", ("bad", [], 1, 1.5, True))
def test_invalid_active_result_shape_blocks_before_dispatch(
    monkeypatch,
    tmp_path,
    result,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task(result=result)
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert control.calls == []


@pytest.mark.parametrize(
    "field,value",
    (("job_id", "other-job"), ("provider", "other-provider")),
)
def test_active_result_identity_mismatch_blocks_before_dispatch(
    monkeypatch,
    tmp_path,
    field,
    value,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task(result={field: value})
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert control.calls == []


@pytest.mark.parametrize(
    "field,replacement",
    (
        ("task_id", "other-task"),
        ("task_type", "image"),
        ("provider", "other-provider"),
        ("metadata", {"scene_id": 1, "shot_id": 99}),
    ),
)
def test_scene_task_receipt_identity_mismatch_blocks_before_dispatch(
    monkeypatch,
    tmp_path,
    field,
    replacement,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    repository.receipts[task["task_id"]][field] = replacement
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert control.calls == []


@pytest.mark.parametrize(
    "field,replacement",
    (
        ("task_id", "other-task"),
        ("task_type", "image"),
        ("job_id", "other-job"),
        ("provider", "other-provider"),
        ("metadata", {"scene_id": 1, "shot_id": 99}),
    ),
)
def test_receipt_terminal_identity_mismatch_blocks_before_dispatch(
    monkeypatch,
    tmp_path,
    field,
    replacement,
):
    (
        module,
        control,
        task,
        repository,
        _,
        _,
        _,
        lifecycle,
    ) = _valid_single_task_setup(
        monkeypatch,
        tmp_path,
        terminal_status="succeeded",
    )
    repository.terminals[task["task_id"]][field] = replacement

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert control.calls == []


def test_unknown_durable_terminal_status_blocks_before_dispatch(
    monkeypatch,
    tmp_path,
):
    (
        module,
        control,
        task,
        repository,
        _,
        _,
        _,
        lifecycle,
    ) = _valid_single_task_setup(
        monkeypatch,
        tmp_path,
        terminal_status="succeeded",
    )
    repository.terminals[task["task_id"]]["status"] = "mystery"

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert control.calls == []


@pytest.mark.parametrize("status", TERMINAL_LOCAL_STATUSES)
def test_terminal_local_task_is_structurally_validated_but_skipped(
    monkeypatch,
    tmp_path,
    status,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task(status=status)
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    returned = lifecycle.advance_once(SCENE_ID)

    assert returned == {
        "scene_id": SCENE_ID,
        "advanced": [],
        "advanced_count": 0,
    }
    assert repository.calls == []
    assert control.initializations == []
    assert control.calls == []


@pytest.mark.parametrize("status", TERMINAL_LOCAL_STATUSES)
@pytest.mark.parametrize("invalid_task_id", (None, "", 7))
def test_terminal_local_task_still_requires_valid_task_identity(
    monkeypatch,
    tmp_path,
    status,
    invalid_task_id,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task(status=status)
    task["task_id"] = invalid_task_id
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert repository.calls == []
    assert control.initializations == []
    assert control.calls == []


def test_empty_scene_returns_exact_empty_envelope_without_dependencies(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    _write_scene(tmp_path, _scene([]))
    repository = FakeRepository()
    resolver = ResolverBomb()
    audit = ObserverBomb()
    events = ObserverBomb()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        resolver,
        audit,
        events,
    )

    returned = lifecycle.advance_once(SCENE_ID)

    assert returned == {
        "scene_id": SCENE_ID,
        "advanced": [],
        "advanced_count": 0,
    }
    assert repository.calls == []
    assert control.initializations == []
    assert resolver.calls == audit.calls == events.calls == 0


def test_mixed_scene_dispatches_only_active_tasks_in_original_order(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    tasks = [
        _task("terminal-a", status="done", shot_id=1),
        _task("active-b", status="waiting", shot_id=2),
        _task("terminal-c", status="failed", shot_id=3),
        _task("active-d", status="running", shot_id=4),
        _task("active-e", status="succeeded", shot_id=5),
    ]
    _write_scene(tmp_path, _scene(tasks))
    active = [tasks[1], tasks[3], tasks[4]]
    repository = FakeRepository(active)
    for task in active:
        repository.set_topology(task["task_id"])
        control.results[task["task_id"]] = {
            "task_id": task["task_id"],
            "action": "poll",
            "result": object(),
        }
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    returned = lifecycle.advance_once(SCENE_ID)

    assert control.calls == ["active-b", "active-d", "active-e"]
    assert returned["advanced"] == [
        control.results["active-b"],
        control.results["active-d"],
        control.results["active-e"],
    ]
    assert all(
        actual is expected
        for actual, expected in zip(
            returned["advanced"],
            [
                control.results["active-b"],
                control.results["active-d"],
                control.results["active-e"],
            ],
        )
    )
    assert returned["advanced_count"] == len(returned["advanced"]) == 3
    assert not any(
        task_id in {"terminal-a", "terminal-c"}
        for _, task_id in repository.calls
    )


def test_valid_scene_pass_does_not_mutate_scene_or_repository_state(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    scene_path = _write_scene(tmp_path, _scene([task]))
    original_scene_bytes = scene_path.read_bytes()
    repository = FakeRepository([task])
    original_receipts = deepcopy(repository.receipts)
    original_terminals = deepcopy(repository.terminals)
    original_retrieved = set(repository.retrieved)
    original_finalized = set(repository.finalized)
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    lifecycle.advance_once(SCENE_ID)

    assert control.calls == [task["task_id"]]
    assert scene_path.read_bytes() == original_scene_bytes
    assert repository.receipts == original_receipts
    assert repository.terminals == original_terminals
    assert repository.retrieved == original_retrieved
    assert repository.finalized == original_finalized


@pytest.mark.parametrize(
    "late_error",
    (
        "missing-receipt",
        "malformed-receipt",
        "receipt-identity",
        "invalid-topology",
        "terminal-identity",
        "unknown-terminal-status",
    ),
)
def test_later_discoverable_error_blocks_every_dispatch(
    monkeypatch,
    tmp_path,
    late_error,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    first = _task("task-a", shot_id=1)
    second = _task("task-b", shot_id=2)
    tasks = [first, second]
    _write_scene(tmp_path, _scene(tasks))
    repository = FakeRepository(tasks)
    repository.set_topology("task-a")
    repository.set_topology("task-b")

    if late_error == "missing-receipt":
        repository.effects[("resume", "task-b")] = (
            GenerationJobRepositoryError("missing late receipt")
        )
    elif late_error == "malformed-receipt":
        repository.effects[("resume", "task-b")] = (
            GenerationJobReceiptError("corrupt late receipt")
        )
    elif late_error == "receipt-identity":
        repository.receipts["task-b"]["provider"] = "other-provider"
    elif late_error == "invalid-topology":
        repository.retrieved.add("task-b")
    else:
        repository.set_topology("task-b", terminal_status="succeeded")
        if late_error == "terminal-identity":
            repository.terminals["task-b"]["job_id"] = "other-job"
        else:
            repository.terminals["task-b"]["status"] = "mystery"

    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert control.initializations == []
    assert control.calls == []


def test_all_preflight_repository_inspection_precedes_first_dispatch(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    trace = []
    control = _install_coordinator(
        monkeypatch,
        module,
        CoordinatorControl(trace=trace),
    )
    tasks = [
        _task("task-a", shot_id=1),
        _task("task-b", shot_id=2),
        _task("task-c", shot_id=3),
    ]
    _write_scene(tmp_path, _scene(tasks))
    repository = FakeRepository(tasks, trace=trace)
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    lifecycle.advance_once(SCENE_ID)

    first_dispatch = trace.index(("coordinator", "advance_once", "task-a"))
    for task in tasks:
        task_id = task["task_id"]
        for operation in (
            "resume",
            "terminal_exists",
            "retrieved_exists",
            "finalized_exists",
        ):
            assert trace.index(("repository", operation, task_id)) < first_dispatch
    assert control.calls == ["task-a", "task-b", "task-c"]


def test_dispatch_plan_remains_fixed_when_first_child_rewrites_scene(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    first = _task("task-a", shot_id=1)
    second = _task("task-b", shot_id=2)
    original = _scene([first, second])
    scene_path = _write_scene(tmp_path, original)
    repository = FakeRepository([first, second])

    first_result = {
        "task_id": "task-a",
        "action": "poll",
        "result": object(),
    }
    second_result = {
        "task_id": "task-b",
        "action": "poll",
        "result": object(),
    }

    def rewrite_scene(_task_id):
        scene_path.write_text(
            json.dumps(_scene([_task("replacement", shot_id=9)])),
            encoding="utf-8",
        )
        return first_result

    control.effects["task-a"] = rewrite_scene
    control.results["task-b"] = second_result
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    returned = lifecycle.advance_once(SCENE_ID)

    assert control.calls == ["task-a", "task-b"]
    assert returned["advanced"][0] is first_result
    assert returned["advanced"][1] is second_result


def test_dispatch_error_stops_later_tasks_without_rollback(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    tasks = [
        _task("task-a", shot_id=1),
        _task("task-b", shot_id=2),
        _task("task-c", shot_id=3),
    ]
    _write_scene(tmp_path, _scene(tasks))
    repository = FakeRepository(tasks)
    original = GenerationLifecycleCoordinatorError("stage 2N failed")
    control.effects["task-b"] = original
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(
        module.GenerationSceneLifecycleError,
        match="task-b",
    ) as exc_info:
        lifecycle.advance_once(SCENE_ID)

    assert exc_info.value.__cause__ is original
    assert control.calls == ["task-a", "task-b"]
    assert "task-c" not in control.calls


@pytest.mark.parametrize(
    "repository_error",
    (
        GenerationJobRepositoryError("missing receipt"),
        GenerationJobReceiptError("malformed receipt"),
    ),
    ids=("missing", "malformed"),
)
def test_known_receipt_error_is_normalized_with_exact_cause(
    monkeypatch,
    tmp_path,
    repository_error,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    repository.effects[("resume", task["task_id"])] = repository_error
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(
        module.GenerationSceneLifecycleError
    ) as exc_info:
        lifecycle.advance_once(SCENE_ID)

    assert exc_info.value.__cause__ is repository_error
    assert control.calls == []


def test_known_terminal_error_is_normalized_with_exact_cause(
    monkeypatch,
    tmp_path,
):
    (
        module,
        control,
        task,
        repository,
        _,
        _,
        _,
        lifecycle,
    ) = _valid_single_task_setup(
        monkeypatch,
        tmp_path,
        terminal_status="succeeded",
    )
    original = GenerationJobTerminalError("malformed terminal")
    repository.effects[("load_terminal", task["task_id"])] = original

    with pytest.raises(
        module.GenerationSceneLifecycleError
    ) as exc_info:
        lifecycle.advance_once(SCENE_ID)

    assert exc_info.value.__cause__ is original
    assert control.calls == []


def test_programming_exception_from_preflight_propagates_unchanged(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    original = ValueError("repository programming defect")
    repository.effects[("terminal_exists", task["task_id"])] = original
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(ValueError) as exc_info:
        lifecycle.advance_once(SCENE_ID)

    assert exc_info.value is original
    assert not isinstance(
        exc_info.value,
        module.GenerationSceneLifecycleError,
    )
    assert control.calls == []


def test_programming_exception_from_coordinator_constructor_propagates(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    task = _task()
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    original = ValueError("coordinator constructor defect")

    class ConstructorBomb:
        def __init__(self, *args, **kwargs):
            raise original

    monkeypatch.setattr(module, "GenerationLifecycleCoordinator", ConstructorBomb)
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(ValueError) as exc_info:
        lifecycle.advance_once(SCENE_ID)

    assert exc_info.value is original


def test_programming_exception_from_dispatch_propagates_unchanged(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    original = ValueError("coordinator programming defect")
    control.effects[task["task_id"]] = original
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(ValueError) as exc_info:
        lifecycle.advance_once(SCENE_ID)

    assert exc_info.value is original
    assert control.calls == [task["task_id"]]


def test_injected_repository_and_optional_observers_preserve_identity(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    task = _task()
    _write_scene(tmp_path, _scene([task]))
    repository = FakeRepository([task])
    resolver = ResolverBomb()
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        resolver,
        None,
        None,
        include_observers=False,
    )

    lifecycle.advance_once(SCENE_ID)

    assert len(control.initializations) == 1
    _assert_exact_dependencies(
        control.initializations[0],
        repository,
        resolver,
        None,
        None,
    )


def test_default_repository_is_constructed_from_project_path(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    _write_scene(tmp_path, _scene([]))
    constructed = []

    class RepositorySpy(FakeRepository):
        def __init__(self, project_path):
            constructed.append(project_path)
            super().__init__()

    monkeypatch.setattr(module, "GenerationJobRepository", RepositorySpy)
    lifecycle = module.GenerationSceneLifecycle(
        tmp_path,
        ResolverBomb(),
    )

    returned = lifecycle.advance_once(SCENE_ID)

    assert constructed == [tmp_path]
    assert returned == {
        "scene_id": SCENE_ID,
        "advanced": [],
        "advanced_count": 0,
    }
    assert control.calls == []


def test_repeat_pass_has_no_scene_lifecycle_cache(
    monkeypatch,
    tmp_path,
):
    module = _load_future_module()
    control = _install_coordinator(monkeypatch, module)
    first = _task("task-a", shot_id=1)
    second = _task("task-b", shot_id=2)
    _write_scene(tmp_path, _scene([first, second]))
    repository = FakeRepository([first, second])
    lifecycle = _make_lifecycle(
        module,
        tmp_path,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    first_result = lifecycle.advance_once(SCENE_ID)
    second_result = lifecycle.advance_once(SCENE_ID)

    assert control.calls == ["task-a", "task-b", "task-a", "task-b"]
    assert first_result["advanced_count"] == 2
    assert second_result["advanced_count"] == 2
    assert [name for name, _ in repository.calls].count("resume") == 4


def test_stage_2o_source_has_no_direct_child_or_forbidden_orchestration():
    module = _load_future_module()
    source = inspect.getsource(module)
    tree = ast.parse(source)

    forbidden_names = {
        "GenerationJobLifecycle",
        "GenerationJobResultLifecycle",
        "GenerationJobAssetLifecycle",
        "GenerationResultReconciler",
        "GenerationTerminalReconciler",
        "GenerationEngine",
        "GenerationQueue",
        "MoviePipeline",
    }
    used_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }
    assert used_names.isdisjoint(forbidden_names)
    assert not any(isinstance(node, ast.While) for node in ast.walk(tree))

    forbidden_attribute_calls = {
        "load_retrieved",
        "load_finalized",
        "persist",
        "persist_terminal",
        "persist_retrieved",
        "persist_finalized",
        "record",
        "emit",
        "replace",
        "write_text",
        "write_bytes",
        "sleep",
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    }
    assert called_attributes.isdisjoint(forbidden_attribute_calls)


def test_future_module_exposes_exact_public_api():
    module = _load_future_module()

    assert issubclass(module.GenerationSceneLifecycleError, RuntimeError)
    signature = inspect.signature(module.GenerationSceneLifecycle)
    assert tuple(signature.parameters) == (
        "project_path",
        "provider_resolver",
        "job_repository",
        "audit",
        "events",
    )
    assert signature.parameters["job_repository"].default is None
    assert signature.parameters["audit"].default is None
    assert signature.parameters["events"].default is None
    assert hasattr(module.GenerationSceneLifecycle, "advance_once")
