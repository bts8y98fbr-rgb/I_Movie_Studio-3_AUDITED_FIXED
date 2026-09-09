import ast
import inspect
import json
from pathlib import Path
import textwrap

import pytest

import core.movie_engine.generation_scene_lifecycle as scene_lifecycle_module
from core.ai_core.generation_job_repository import (
    GenerationJobRepositoryError,
)
from core.movie_engine.generation_lifecycle_coordinator import (
    GenerationLifecycleCoordinatorError,
)
from core.movie_engine.generation_scene_lifecycle import (
    GenerationSceneLifecycle,
    GenerationSceneLifecycleError,
)


SCENE_ID = 1
PROVIDER = "deterministic-remote-video"


class ResolverBomb:
    def get(self, *_args, **_kwargs):
        raise AssertionError("inspect must not resolve a provider")

    def __getattr__(self, name):
        raise AssertionError(f"inspect must not access provider API {name}")


class ObserverBomb:
    def record(self, *_args, **_kwargs):
        raise AssertionError("inspect must not emit audit records")

    def emit(self, *_args, **_kwargs):
        raise AssertionError("inspect must not emit project events")


class TransitionBomb:
    def __init__(self, *_args, **_kwargs):
        raise AssertionError("inspect must not construct transition children")


class CoordinatorConstructionBomb:
    calls = []

    def __init__(self, *_args, **_kwargs):
        self.calls.append((_args, _kwargs))
        raise AssertionError("inspect must not construct Stage 2N")


class FakeRepository:
    def __init__(
        self,
        submitted=None,
        terminals=None,
        retrieved=None,
        finalized=None,
        errors=None,
        trace=None,
    ):
        self.submitted = dict(submitted or {})
        self.terminals = dict(terminals or {})
        self.retrieved = set(retrieved or ())
        self.finalized = set(finalized or ())
        self.errors = dict(errors or {})
        self.trace = trace if trace is not None else []
        self.write_calls = []

    def _read(self, operation, task_id, value):
        self.trace.append(("repository", operation, task_id))
        error = self.errors.get((operation, task_id))
        if error is not None:
            raise error
        return value

    def resume(self, task_id):
        if task_id not in self.submitted:
            error = GenerationJobRepositoryError(
                f"submitted receipt missing for {task_id}"
            )
            return self._raise_read("resume", task_id, error)
        return self._read("resume", task_id, self.submitted[task_id])

    def _raise_read(self, operation, task_id, error):
        self.trace.append(("repository", operation, task_id))
        configured = self.errors.get((operation, task_id))
        raise configured if configured is not None else error

    def terminal_exists(self, task_id):
        return self._read(
            "terminal_exists",
            task_id,
            task_id in self.terminals,
        )

    def load_terminal(self, task_id):
        return self._read("load_terminal", task_id, self.terminals[task_id])

    def retrieved_exists(self, task_id):
        return self._read(
            "retrieved_exists",
            task_id,
            task_id in self.retrieved,
        )

    def finalized_exists(self, task_id):
        return self._read(
            "finalized_exists",
            task_id,
            task_id in self.finalized,
        )

    def load_retrieved(self, *_args, **_kwargs):
        raise AssertionError("Stage 2Q must not load retrieved payloads")

    def load_finalized(self, *_args, **_kwargs):
        raise AssertionError("Stage 2Q must not load finalized payloads")

    def _write_bomb(self, operation, *_args, **_kwargs):
        self.write_calls.append(operation)
        raise AssertionError(f"inspect must not call repository.{operation}")

    def persist(self, *args, **kwargs):
        return self._write_bomb("persist", *args, **kwargs)

    def persist_terminal(self, *args, **kwargs):
        return self._write_bomb("persist_terminal", *args, **kwargs)

    def persist_retrieved(self, *args, **kwargs):
        return self._write_bomb("persist_retrieved", *args, **kwargs)

    def persist_finalized(self, *args, **kwargs):
        return self._write_bomb("persist_finalized", *args, **kwargs)

    def _atomic_write(self, *args, **kwargs):
        return self._write_bomb("_atomic_write", *args, **kwargs)


class CoordinatorInstanceSpy:
    def __init__(self, factory):
        self.factory = factory

    def advance_once(self, task_id):
        self.factory.trace.append(("coordinator", "advance_once", task_id))
        self.factory.advance_calls.append(task_id)
        callback = self.factory.callbacks.get(task_id)
        if callback is not None:
            callback()
        error = self.factory.errors.get(task_id)
        if error is not None:
            raise error
        return self.factory.results[task_id]


class CoordinatorFactorySpy:
    def __init__(
        self,
        results,
        errors=None,
        callbacks=None,
        trace=None,
    ):
        self.results = dict(results)
        self.errors = dict(errors or {})
        self.callbacks = dict(callbacks or {})
        self.trace = trace if trace is not None else []
        self.constructor_calls = []
        self.advance_calls = []

    def __call__(self, *args, **kwargs):
        self.trace.append(("coordinator", "construct"))
        self.constructor_calls.append((args, kwargs))
        return CoordinatorInstanceSpy(self)


def make_task(
    task_id="task-001",
    status="submitted",
    scene_id=SCENE_ID,
    shot_id=1,
    task_type="video",
    provider=PROVIDER,
    result=None,
):
    return {
        "task_id": task_id,
        "type": task_type,
        "status": status,
        "provider": provider,
        "metadata": {
            "scene_id": scene_id,
            "shot_id": shot_id,
        },
        "result": result,
        "quality": "4k",
    }


def make_receipt(task):
    return {
        "task_id": task["task_id"],
        "task_type": task["type"],
        "job_id": f"job-{task['task_id']}",
        "provider": task["provider"],
        "metadata": dict(task["metadata"]),
    }


def make_terminal(receipt, status):
    return {
        "task_id": receipt["task_id"],
        "task_type": receipt["task_type"],
        "job_id": receipt["job_id"],
        "provider": receipt["provider"],
        "metadata": dict(receipt["metadata"]),
        "status": status,
    }


def write_scene(project_path, tasks, scene_id=SCENE_ID, **extra):
    path = (
        project_path
        / "render_output"
        / f"scene_{scene_id:03d}"
        / "generation_result.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "scene_id": scene_id,
        "tasks": tasks,
        "future_scene_field": {"preserve": True},
        **extra,
    }
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def make_repository_for_tasks(tasks):
    submitted = {
        task["task_id"]: make_receipt(task)
        for task in tasks
        if task.get("status")
        not in scene_lifecycle_module.TERMINAL_LOCAL_STATUSES
    }
    return FakeRepository(submitted=submitted)


def make_lifecycle(project_path, repository):
    return GenerationSceneLifecycle(
        project_path=project_path,
        provider_resolver=ResolverBomb(),
        job_repository=repository,
        audit=ObserverBomb(),
        events=ObserverBomb(),
    )


def call_future_inspect(lifecycle, scene_id=SCENE_ID):
    method = getattr(lifecycle, "inspect", None)
    assert callable(method), (
        "Stage 2Q RED: GenerationSceneLifecycle.inspect is missing"
    )
    return method(scene_id)


def snapshot_project_tree(project_path):
    directories = []
    files = {}
    for path in sorted(project_path.rglob("*")):
        relative = path.relative_to(project_path).as_posix()
        if path.is_dir():
            directories.append(relative)
        else:
            files[relative] = path.read_bytes()
    return {
        "directories": tuple(directories),
        "files": files,
    }


def install_inspection_bombs(monkeypatch):
    CoordinatorConstructionBomb.calls = []
    monkeypatch.setattr(
        scene_lifecycle_module,
        "GenerationLifecycleCoordinator",
        CoordinatorConstructionBomb,
    )
    for name in (
        "GenerationJobLifecycle",
        "GenerationJobResultLifecycle",
        "GenerationJobAssetLifecycle",
        "GenerationResultReconciler",
        "GenerationTerminalReconciler",
    ):
        monkeypatch.setattr(
            scene_lifecycle_module,
            name,
            TransitionBomb,
            raising=False,
        )


def expected_inspection(task_id, action):
    return {
        "scene_id": SCENE_ID,
        "active_count": 1,
        "needs_advance": True,
        "plan": [
            {
                "task_id": task_id,
                "action": action,
            }
        ],
    }


@pytest.mark.parametrize(
    (
        "terminal_status",
        "retrieved",
        "finalized",
        "expected_action",
    ),
    [
        (None, False, False, "poll"),
        ("failed", False, False, "reconcile_terminal"),
        ("cancelled", False, False, "reconcile_terminal"),
        ("succeeded", False, False, "retrieve"),
        ("succeeded", True, False, "finalize"),
        ("succeeded", True, True, "reconcile_success"),
    ],
)
def test_inspect_returns_exact_plan_for_valid_topology(
    tmp_path,
    monkeypatch,
    terminal_status,
    retrieved,
    finalized,
    expected_action,
):
    task = make_task()
    receipt = make_receipt(task)
    repository = FakeRepository(
        submitted={task["task_id"]: receipt},
        terminals=(
            {task["task_id"]: make_terminal(receipt, terminal_status)}
            if terminal_status is not None
            else {}
        ),
        retrieved={task["task_id"]} if retrieved else set(),
        finalized={task["task_id"]} if finalized else set(),
    )
    write_scene(tmp_path, [task])
    install_inspection_bombs(monkeypatch)

    actual = call_future_inspect(make_lifecycle(tmp_path, repository))

    assert actual == expected_inspection(task["task_id"], expected_action)
    assert set(actual) == {
        "scene_id",
        "active_count",
        "needs_advance",
        "plan",
    }
    assert set(actual["plan"][0]) == {"task_id", "action"}
    assert actual["active_count"] == len(actual["plan"])
    assert actual["needs_advance"] is bool(actual["plan"])
    assert repository.write_calls == []
    assert CoordinatorConstructionBomb.calls == []


def test_inspect_terminal_only_scene_returns_exact_empty_result(
    tmp_path,
    monkeypatch,
):
    tasks = [
        {"task_id": "done-task", "status": "done"},
        {"task_id": "failed-task", "status": "failed"},
        {"task_id": "cancelled-task", "status": "cancelled"},
    ]
    repository = FakeRepository()
    write_scene(tmp_path, tasks)
    install_inspection_bombs(monkeypatch)

    actual = call_future_inspect(make_lifecycle(tmp_path, repository))

    assert actual == {
        "scene_id": SCENE_ID,
        "active_count": 0,
        "needs_advance": False,
        "plan": [],
    }
    assert repository.trace == []
    assert CoordinatorConstructionBomb.calls == []


def test_inspect_preserves_active_order_and_skips_terminal_tasks(
    tmp_path,
    monkeypatch,
):
    active_b = make_task("active-b", status="waiting", shot_id=2)
    active_d = make_task("active-d", status="running", shot_id=4)
    active_e = make_task("active-e", status="succeeded", shot_id=5)
    tasks = [
        {"task_id": "terminal-a", "status": "done"},
        active_b,
        {"task_id": "terminal-c", "status": "failed"},
        active_d,
        active_e,
    ]
    receipts = {
        task["task_id"]: make_receipt(task)
        for task in (active_b, active_d, active_e)
    }
    terminals = {
        "active-d": make_terminal(receipts["active-d"], "succeeded"),
        "active-e": make_terminal(receipts["active-e"], "cancelled"),
    }
    repository = FakeRepository(
        submitted=receipts,
        terminals=terminals,
    )
    write_scene(tmp_path, tasks)
    install_inspection_bombs(monkeypatch)

    actual = call_future_inspect(make_lifecycle(tmp_path, repository))

    assert actual == {
        "scene_id": SCENE_ID,
        "active_count": 3,
        "needs_advance": True,
        "plan": [
            {"task_id": "active-b", "action": "poll"},
            {"task_id": "active-d", "action": "retrieve"},
            {"task_id": "active-e", "action": "reconcile_terminal"},
        ],
    }
    resumed = [
        task_id
        for owner, operation, task_id in repository.trace
        if owner == "repository" and operation == "resume"
    ]
    assert resumed == ["active-b", "active-d", "active-e"]


@pytest.mark.parametrize(
    ("terminal_status", "retrieved", "finalized"),
    [
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
        ("unknown", False, False),
    ],
)
def test_inspect_rejects_invalid_topology_before_coordinator(
    tmp_path,
    monkeypatch,
    terminal_status,
    retrieved,
    finalized,
):
    task = make_task()
    receipt = make_receipt(task)
    repository = FakeRepository(
        submitted={task["task_id"]: receipt},
        terminals=(
            {task["task_id"]: make_terminal(receipt, terminal_status)}
            if terminal_status is not None
            else {}
        ),
        retrieved={task["task_id"]} if retrieved else set(),
        finalized={task["task_id"]} if finalized else set(),
    )
    write_scene(tmp_path, [task])
    install_inspection_bombs(monkeypatch)

    with pytest.raises(GenerationSceneLifecycleError):
        call_future_inspect(make_lifecycle(tmp_path, repository))

    assert repository.write_calls == []
    assert CoordinatorConstructionBomb.calls == []


IDENTITY_CASES = (
    "document-scene-id",
    "duplicate-task-id",
    "empty-task-id",
    "invalid-task-type",
    "invalid-provider",
    "metadata-not-dict",
    "task-metadata-scene-id",
    "missing-shot-id",
    "result-shape",
    "unknown-local-status",
    "receipt-task-id",
    "receipt-task-type",
    "receipt-provider",
    "receipt-metadata-scene-id",
    "receipt-metadata-shot-id",
    "result-job-id",
    "result-provider",
    "terminal-task-id",
    "terminal-task-type",
    "terminal-job-id",
    "terminal-provider",
    "terminal-metadata",
)


@pytest.mark.parametrize("case", IDENTITY_CASES)
def test_inspect_rejects_identity_and_shape_defects_without_partial_result(
    tmp_path,
    monkeypatch,
    case,
):
    task = make_task()
    receipt = make_receipt(task)
    terminal = make_terminal(receipt, "succeeded")
    tasks = [task]
    scene_id = SCENE_ID

    if case == "document-scene-id":
        scene_id = 2
    elif case == "duplicate-task-id":
        tasks = [task, dict(task)]
    elif case == "empty-task-id":
        task["task_id"] = ""
    elif case == "invalid-task-type":
        task["type"] = ""
    elif case == "invalid-provider":
        task["provider"] = None
    elif case == "metadata-not-dict":
        task["metadata"] = []
    elif case == "task-metadata-scene-id":
        task["metadata"]["scene_id"] = 99
    elif case == "missing-shot-id":
        del task["metadata"]["shot_id"]
    elif case == "result-shape":
        task["result"] = "not-a-dictionary"
    elif case == "unknown-local-status":
        task["status"] = "provider-weird"
    elif case == "receipt-task-id":
        receipt["task_id"] = "other-task"
    elif case == "receipt-task-type":
        receipt["task_type"] = "audio"
    elif case == "receipt-provider":
        receipt["provider"] = "other-provider"
    elif case == "receipt-metadata-scene-id":
        receipt["metadata"]["scene_id"] = 99
    elif case == "receipt-metadata-shot-id":
        receipt["metadata"]["shot_id"] = 99
    elif case == "result-job-id":
        task["result"] = {"job_id": "other-job"}
    elif case == "result-provider":
        task["result"] = {"provider": "other-provider"}
    elif case == "terminal-task-id":
        terminal["task_id"] = "other-task"
    elif case == "terminal-task-type":
        terminal["task_type"] = "audio"
    elif case == "terminal-job-id":
        terminal["job_id"] = "other-job"
    elif case == "terminal-provider":
        terminal["provider"] = "other-provider"
    elif case == "terminal-metadata":
        terminal["metadata"] = {"scene_id": SCENE_ID, "shot_id": 99}

    repository = FakeRepository(
        submitted={"task-001": receipt},
        terminals={"task-001": terminal},
    )
    path = write_scene(tmp_path, tasks)
    if case == "document-scene-id":
        document = json.loads(path.read_text(encoding="utf-8"))
        document["scene_id"] = scene_id
        path.write_text(json.dumps(document), encoding="utf-8")
    install_inspection_bombs(monkeypatch)

    with pytest.raises(GenerationSceneLifecycleError):
        call_future_inspect(make_lifecycle(tmp_path, repository))

    assert repository.write_calls == []
    assert CoordinatorConstructionBomb.calls == []


@pytest.mark.parametrize("scene_id", [True, False, 0, -1, 1.5, "1", None])
def test_inspect_rejects_invalid_scene_identity_before_repository(
    tmp_path,
    monkeypatch,
    scene_id,
):
    repository = FakeRepository()
    install_inspection_bombs(monkeypatch)

    with pytest.raises(GenerationSceneLifecycleError):
        call_future_inspect(make_lifecycle(tmp_path, repository), scene_id)

    assert repository.trace == []
    assert CoordinatorConstructionBomb.calls == []


@pytest.mark.parametrize(
    "document_bytes",
    [None, b"{broken", b"[]", b"\xff"],
)
def test_inspect_rejects_missing_or_corrupt_scene_document(
    tmp_path,
    monkeypatch,
    document_bytes,
):
    if document_bytes is not None:
        path = (
            tmp_path
            / "render_output"
            / "scene_001"
            / "generation_result.json"
        )
        path.parent.mkdir(parents=True)
        path.write_bytes(document_bytes)
    repository = FakeRepository()
    install_inspection_bombs(monkeypatch)

    with pytest.raises(GenerationSceneLifecycleError):
        call_future_inspect(make_lifecycle(tmp_path, repository))

    assert repository.trace == []
    assert CoordinatorConstructionBomb.calls == []


def test_inspect_late_preflight_failure_returns_no_partial_plan_or_dispatch(
    tmp_path,
    monkeypatch,
):
    first = make_task("task-first", shot_id=1)
    later = make_task("task-later", shot_id=2)
    first_receipt = make_receipt(first)
    later_receipt = make_receipt(later)
    later_receipt["provider"] = "mismatched-provider"
    repository = FakeRepository(
        submitted={
            "task-first": first_receipt,
            "task-later": later_receipt,
        }
    )
    write_scene(tmp_path, [first, later])
    install_inspection_bombs(monkeypatch)

    with pytest.raises(GenerationSceneLifecycleError):
        call_future_inspect(make_lifecycle(tmp_path, repository))

    assert CoordinatorConstructionBomb.calls == []
    assert repository.write_calls == []


def test_inspect_is_byte_for_byte_observational_and_calls_no_side_effects(
    tmp_path,
    monkeypatch,
):
    task = make_task(result={"job_id": "job-task-001", "provider": PROVIDER})
    receipt = make_receipt(task)
    repository = FakeRepository(
        submitted={task["task_id"]: receipt},
        terminals={
            task["task_id"]: make_terminal(receipt, "succeeded")
        },
        retrieved={task["task_id"]},
        finalized={task["task_id"]},
    )
    write_scene(tmp_path, [task])
    artifacts = {
        "generation_jobs/submitted/task-001.json": b"submitted-bytes\n",
        "generation_jobs/terminal/task-001.json": b"terminal-bytes\n",
        "generation_jobs/retrieved/task-001.json": b"retrieved-bytes\n",
        "generation_jobs/finalized/task-001.json": b"finalized-bytes\n",
        "assets/registry.json": b"registry-bytes\n",
        "assets/versions/asset-001-v1.json": b"version-bytes\n",
        "assets/media/asset-001.mp4": b"asset-bytes\x00\x01",
        "render/scene_001/render_plan.json": b"render-plan-bytes\n",
    }
    for relative, content in artifacts.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    before = snapshot_project_tree(tmp_path)
    install_inspection_bombs(monkeypatch)
    lifecycle = make_lifecycle(tmp_path, repository)
    monkeypatch.setattr(
        lifecycle,
        "advance_once",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("inspect must not call advance_once")
        ),
    )

    result = call_future_inspect(lifecycle)

    assert result["plan"] == [
        {"task_id": "task-001", "action": "reconcile_success"}
    ]
    assert snapshot_project_tree(tmp_path) == before
    assert repository.write_calls == []
    assert CoordinatorConstructionBomb.calls == []


def test_inspect_normalizes_repository_error_with_exact_cause(
    tmp_path,
    monkeypatch,
):
    task = make_task()
    original = GenerationJobRepositoryError("corrupt submitted receipt")
    repository = FakeRepository(
        submitted={task["task_id"]: make_receipt(task)},
        errors={("resume", task["task_id"]): original},
    )
    write_scene(tmp_path, [task])
    install_inspection_bombs(monkeypatch)

    with pytest.raises(GenerationSceneLifecycleError) as exc_info:
        call_future_inspect(make_lifecycle(tmp_path, repository))

    assert exc_info.value.__cause__ is original
    assert CoordinatorConstructionBomb.calls == []


def test_inspect_does_not_wrap_programming_error(
    tmp_path,
    monkeypatch,
):
    task = make_task()
    original = ValueError("repository programming defect")
    repository = FakeRepository(
        submitted={task["task_id"]: make_receipt(task)},
        errors={("terminal_exists", task["task_id"]): original},
    )
    write_scene(tmp_path, [task])
    install_inspection_bombs(monkeypatch)

    with pytest.raises(ValueError) as exc_info:
        call_future_inspect(make_lifecycle(tmp_path, repository))

    assert exc_info.value is original
    assert CoordinatorConstructionBomb.calls == []


def self_method_calls(method):
    node = ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]
    return {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and isinstance(child.func.value, ast.Name)
        and child.func.value.id == "self"
    }, node


def test_inspect_and_advance_use_one_shared_uncached_preflight_helper():
    inspect_method = getattr(GenerationSceneLifecycle, "inspect", None)
    assert callable(inspect_method), (
        "Stage 2Q RED: GenerationSceneLifecycle.inspect is missing"
    )
    inspect_calls, inspect_node = self_method_calls(inspect_method)
    advance_calls, advance_node = self_method_calls(
        GenerationSceneLifecycle.advance_once
    )
    shared_private_calls = {
        name
        for name in inspect_calls & advance_calls
        if name.startswith("_")
    }
    assert len(shared_private_calls) == 1

    duplicated_preflight_calls = {
        "_validate_scene_id",
        "_load_scene_document",
        "_validate_scene_document",
        "_preflight_active_task",
        "_planned_action",
    }
    assert not duplicated_preflight_calls.intersection(inspect_calls)
    assert not duplicated_preflight_calls.intersection(advance_calls)

    forbidden_inspect_symbols = {
        "GenerationLifecycleCoordinator",
        "advance_once",
        "poll_once",
        "retrieve_once",
        "finalize_once",
        "reconcile_once",
        "record",
        "emit",
        "persist",
        "persist_terminal",
        "persist_retrieved",
        "persist_finalized",
        "get",
        "sleep",
    }
    inspect_symbols = {
        child.id
        for child in ast.walk(inspect_node)
        if isinstance(child, ast.Name)
    }
    inspect_symbols.update(
        child.attr
        for child in ast.walk(inspect_node)
        if isinstance(child, ast.Attribute)
    )
    assert not forbidden_inspect_symbols.intersection(inspect_symbols)

    forbidden_flow = (
        ast.AsyncFor,
        ast.AsyncFunctionDef,
        ast.AsyncWith,
        ast.Await,
        ast.Try,
        ast.While,
        ast.With,
        ast.Yield,
        ast.YieldFrom,
    )
    assert not any(
        isinstance(child, forbidden_flow)
        for child in ast.walk(inspect_node)
        if child is not inspect_node
    )

    for node in (inspect_node, advance_node):
        for child in ast.walk(node):
            if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = (
                    child.targets
                    if isinstance(child, ast.Assign)
                    else [child.target]
                )
                for target in targets:
                    assert not any(
                        isinstance(nested, ast.Attribute)
                        and isinstance(nested.value, ast.Name)
                        and nested.value.id == "self"
                        for nested in ast.walk(target)
                    )


def build_consistency_topology(tmp_path):
    poll_task = make_task("poll-task", status="waiting", shot_id=1)
    retrieve_task = make_task("retrieve-task", status="running", shot_id=2)
    finalize_task = make_task("finalize-task", status="succeeded", shot_id=3)
    success_task = make_task("success-task", status="succeeded", shot_id=4)
    failed_task = make_task("failed-task", status="processing", shot_id=5)
    tasks = [
        poll_task,
        retrieve_task,
        finalize_task,
        success_task,
        failed_task,
    ]
    receipts = {task["task_id"]: make_receipt(task) for task in tasks}
    terminals = {
        "retrieve-task": make_terminal(receipts["retrieve-task"], "succeeded"),
        "finalize-task": make_terminal(receipts["finalize-task"], "succeeded"),
        "success-task": make_terminal(receipts["success-task"], "succeeded"),
        "failed-task": make_terminal(receipts["failed-task"], "failed"),
    }
    repository = FakeRepository(
        submitted=receipts,
        terminals=terminals,
        retrieved={"finalize-task", "success-task"},
        finalized={"success-task"},
    )
    write_scene(tmp_path, tasks)
    actions = {
        "poll-task": "poll",
        "retrieve-task": "retrieve",
        "finalize-task": "finalize",
        "success-task": "reconcile_success",
        "failed-task": "reconcile_terminal",
    }
    return repository, actions


def test_inspect_plan_matches_real_advance_once_on_unchanged_topology(
    tmp_path,
    monkeypatch,
):
    repository, actions = build_consistency_topology(tmp_path)
    lifecycle = make_lifecycle(tmp_path, repository)

    inspection = call_future_inspect(lifecycle)

    results = {
        task_id: {
            "task_id": task_id,
            "action": action,
            "result": object(),
        }
        for task_id, action in actions.items()
    }
    factory = CoordinatorFactorySpy(results)
    monkeypatch.setattr(
        scene_lifecycle_module,
        "GenerationLifecycleCoordinator",
        factory,
    )
    advanced = lifecycle.advance_once(SCENE_ID)

    assert [item["task_id"] for item in inspection["plan"]] == [
        item["task_id"] for item in advanced["advanced"]
    ]
    assert [item["action"] for item in inspection["plan"]] == [
        item["action"] for item in advanced["advanced"]
    ]


def test_advance_repreflights_and_never_trusts_prior_inspection(
    tmp_path,
    monkeypatch,
):
    task = make_task()
    repository = make_repository_for_tasks([task])
    write_scene(tmp_path, [task])
    lifecycle = make_lifecycle(tmp_path, repository)

    inspection = call_future_inspect(lifecycle)
    assert inspection["plan"] == [
        {"task_id": task["task_id"], "action": "poll"}
    ]

    repository.retrieved.add(task["task_id"])
    factory = CoordinatorFactorySpy({})
    monkeypatch.setattr(
        scene_lifecycle_module,
        "GenerationLifecycleCoordinator",
        factory,
    )

    with pytest.raises(GenerationSceneLifecycleError):
        lifecycle.advance_once(SCENE_ID)

    assert factory.constructor_calls == []
    assert factory.advance_calls == []
    assert [
        call
        for call in repository.trace
        if call[1] == "resume"
    ] == [
        ("repository", "resume", task["task_id"]),
        ("repository", "resume", task["task_id"]),
    ]


def test_existing_advance_completes_all_preflight_before_first_dispatch(
    tmp_path,
    monkeypatch,
):
    trace = []
    first = make_task("task-a", shot_id=1)
    second = make_task("task-b", shot_id=2)
    repository = FakeRepository(
        submitted={
            "task-a": make_receipt(first),
            "task-b": make_receipt(second),
        },
        trace=trace,
    )
    write_scene(tmp_path, [first, second])
    factory = CoordinatorFactorySpy(
        {
            "task-a": {"task_id": "task-a", "action": "poll", "result": {}},
            "task-b": {"task_id": "task-b", "action": "poll", "result": {}},
        },
        trace=trace,
    )
    monkeypatch.setattr(
        scene_lifecycle_module,
        "GenerationLifecycleCoordinator",
        factory,
    )

    make_lifecycle(tmp_path, repository).advance_once(SCENE_ID)

    first_dispatch = trace.index(("coordinator", "advance_once", "task-a"))
    last_preflight = trace.index(
        ("repository", "finalized_exists", "task-b")
    )
    assert last_preflight < first_dispatch
    assert factory.advance_calls == ["task-a", "task-b"]


def test_existing_advance_late_preflight_error_constructs_no_coordinator(
    tmp_path,
    monkeypatch,
):
    first = make_task("task-a", shot_id=1)
    later = make_task("task-b", shot_id=2)
    receipts = {
        "task-a": make_receipt(first),
        "task-b": make_receipt(later),
    }
    repository = FakeRepository(
        submitted=receipts,
        terminals={
            "task-b": make_terminal(receipts["task-b"], "unknown")
        },
    )
    write_scene(tmp_path, [first, later])
    factory = CoordinatorFactorySpy({})
    monkeypatch.setattr(
        scene_lifecycle_module,
        "GenerationLifecycleCoordinator",
        factory,
    )

    with pytest.raises(GenerationSceneLifecycleError):
        make_lifecycle(tmp_path, repository).advance_once(SCENE_ID)

    assert factory.constructor_calls == []
    assert factory.advance_calls == []


def test_existing_advance_dispatch_failure_is_fail_fast_without_rollback(
    tmp_path,
    monkeypatch,
):
    tasks = [
        make_task("task-a", shot_id=1),
        make_task("task-b", shot_id=2),
        make_task("task-c", shot_id=3),
    ]
    repository = make_repository_for_tasks(tasks)
    write_scene(tmp_path, tasks)
    original = GenerationLifecycleCoordinatorError("task-b failed")
    results = {
        task["task_id"]: {
            "task_id": task["task_id"],
            "action": "poll",
            "result": object(),
        }
        for task in tasks
    }
    factory = CoordinatorFactorySpy(
        results,
        errors={"task-b": original},
    )
    monkeypatch.setattr(
        scene_lifecycle_module,
        "GenerationLifecycleCoordinator",
        factory,
    )

    with pytest.raises(GenerationSceneLifecycleError) as exc_info:
        make_lifecycle(tmp_path, repository).advance_once(SCENE_ID)

    assert exc_info.value.__cause__ is original
    assert factory.advance_calls == ["task-a", "task-b"]


def test_existing_advance_dispatches_from_immutable_preflight_snapshot(
    tmp_path,
    monkeypatch,
):
    first = make_task("task-a", shot_id=1)
    second = make_task("task-b", shot_id=2)
    tasks = [first, second]
    repository = make_repository_for_tasks(tasks)
    scene_path = write_scene(tmp_path, tasks)

    def rewrite_scene_after_first_dispatch():
        scene_path.write_text(
            json.dumps({"scene_id": SCENE_ID, "tasks": [first]}),
            encoding="utf-8",
        )

    results = {
        task["task_id"]: {
            "task_id": task["task_id"],
            "action": "poll",
            "result": object(),
        }
        for task in tasks
    }
    factory = CoordinatorFactorySpy(
        results,
        callbacks={"task-a": rewrite_scene_after_first_dispatch},
    )
    monkeypatch.setattr(
        scene_lifecycle_module,
        "GenerationLifecycleCoordinator",
        factory,
    )

    returned = make_lifecycle(tmp_path, repository).advance_once(SCENE_ID)

    assert factory.advance_calls == ["task-a", "task-b"]
    assert returned["advanced"] == [results["task-a"], results["task-b"]]
