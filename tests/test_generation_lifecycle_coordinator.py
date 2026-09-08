from copy import deepcopy
import ast
import importlib
import inspect

import pytest

from core.ai_core.generation_job_asset_lifecycle import (
    GenerationJobAssetLifecycleError,
)
from core.ai_core.generation_job_lifecycle import (
    GenerationJobLifecycleError,
)
from core.ai_core.generation_job_repository import (
    GenerationJobReceiptError,
    GenerationJobRepositoryError,
    GenerationJobTerminalError,
)
from core.ai_core.generation_job_result_lifecycle import (
    GenerationJobResultLifecycleError,
)
from core.movie_engine.generation_result_reconciler import (
    GenerationResultReconciliationError,
)
from core.movie_engine.generation_terminal_reconciler import (
    GenerationTerminalReconciliationError,
)


FUTURE_MODULE = (
    "core.movie_engine.generation_lifecycle_coordinator"
)
TASK_ID = "task-001"

CHILD_SPECS = {
    "GenerationJobLifecycle": ("poll_once", True),
    "GenerationJobResultLifecycle": ("retrieve_once", True),
    "GenerationJobAssetLifecycle": ("finalize_once", False),
    "GenerationResultReconciler": ("reconcile_once", False),
    "GenerationTerminalReconciler": ("reconcile_once", False),
}

ACTION_CHILD = {
    "poll": "GenerationJobLifecycle",
    "retrieve": "GenerationJobResultLifecycle",
    "finalize": "GenerationJobAssetLifecycle",
    "reconcile_success": "GenerationResultReconciler",
    "reconcile_terminal": "GenerationTerminalReconciler",
}

VALID_ROUTES = (
    ("poll", None, False, False),
    ("reconcile_terminal", "failed", False, False),
    ("reconcile_terminal", "cancelled", False, False),
    ("retrieve", "succeeded", False, False),
    ("finalize", "succeeded", True, False),
    ("reconcile_success", "succeeded", True, True),
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


def _submitted(task_id=TASK_ID):
    return {
        "format_version": 1,
        "task_id": str(task_id),
        "task_type": "video",
        "status": "submitted",
        "job_id": "job-001",
        "provider": "deterministic-video",
        "metadata": {
            "scene_id": 1,
            "shot_id": 2,
        },
        "submitted_at": "2026-09-08T00:00:00+00:00",
    }


def _terminal(status="succeeded", task_id=TASK_ID):
    record = {
        "format_version": 1,
        "task_id": str(task_id),
        "task_type": "video",
        "job_id": "job-001",
        "provider": "deterministic-video",
        "status": status,
        "metadata": {
            "scene_id": 1,
            "shot_id": 2,
        },
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


class FakeRepository:
    def __init__(
        self,
        *,
        submitted=None,
        terminal_status=None,
        retrieved=False,
        finalized=False,
    ):
        self.submitted = (
            deepcopy(submitted)
            if submitted is not None
            else _submitted()
        )
        self.terminal = (
            _terminal(terminal_status)
            if terminal_status is not None
            else None
        )
        self.has_terminal = terminal_status is not None
        self.has_retrieved = retrieved
        self.has_finalized = finalized
        self.effects = {}
        self.calls = []

    def _value(self, name, value, *args):
        self.calls.append((name, args))
        effect = self.effects.get(name)
        if isinstance(effect, BaseException):
            raise effect
        if callable(effect):
            return effect(*args)
        return deepcopy(value)

    def resume(self, task_id):
        return self._value("resume", self.submitted, task_id)

    def terminal_exists(self, task_id):
        return self._value(
            "terminal_exists",
            self.has_terminal,
            task_id,
        )

    def load_terminal(self, task_id):
        return self._value("load_terminal", self.terminal, task_id)

    def retrieved_exists(self, task_id):
        return self._value(
            "retrieved_exists",
            self.has_retrieved,
            task_id,
        )

    def finalized_exists(self, task_id):
        return self._value(
            "finalized_exists",
            self.has_finalized,
            task_id,
        )

    def load_retrieved(self, task_id):
        raise AssertionError(
            "Coordinator must not load retrieved payloads"
        )

    def load_finalized(self, task_id):
        raise AssertionError(
            "Coordinator must not load finalized payloads"
        )

    def persist(self, *args, **kwargs):
        raise AssertionError("Coordinator must not persist receipts")

    def persist_terminal(self, *args, **kwargs):
        raise AssertionError("Coordinator must not persist terminal state")

    def persist_retrieved(self, *args, **kwargs):
        raise AssertionError("Coordinator must not persist retrieved state")

    def persist_finalized(self, *args, **kwargs):
        raise AssertionError("Coordinator must not persist finalized state")


class ResolverBomb:
    def __init__(self):
        self.calls = 0

    def get(self, name):
        self.calls += 1
        raise AssertionError(
            "Coordinator must not resolve providers directly"
        )


class ObserverBomb:
    def __init__(self):
        self.calls = 0

    def record(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError(
            "Coordinator must not record duplicate observability"
        )

    def emit(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError(
            "Coordinator must not emit duplicate observability"
        )


class ChildControl:
    def __init__(self, symbol, method_name, uses_resolver):
        self.symbol = symbol
        self.method_name = method_name
        self.uses_resolver = uses_resolver
        self.result = {
            "child": symbol,
        }
        self.error = None
        self.initializations = []
        self.calls = []


def _load_future_module():
    return importlib.import_module(FUTURE_MODULE)


def _child_class(control):
    class ChildSpy:
        def __init__(self, *args, **kwargs):
            control.initializations.append((args, kwargs))

    def child_call(self, task_id):
        control.calls.append(task_id)
        if control.error is not None:
            raise control.error
        return control.result

    setattr(ChildSpy, control.method_name, child_call)
    return ChildSpy


def _install_child_spies(monkeypatch, module):
    controls = {}
    for symbol, (method_name, uses_resolver) in CHILD_SPECS.items():
        control = ChildControl(
            symbol,
            method_name,
            uses_resolver,
        )
        controls[symbol] = control
        monkeypatch.setattr(
            module,
            symbol,
            _child_class(control),
        )
    return controls


def _make_coordinator(
    module,
    repository,
    resolver,
    audit,
    events,
    *,
    include_observers=True,
):
    if include_observers:
        return module.GenerationLifecycleCoordinator(
            repository,
            resolver,
            audit=audit,
            events=events,
        )
    return module.GenerationLifecycleCoordinator(
        repository,
        resolver,
    )


def _argument(initialization, name, position):
    args, kwargs = initialization
    if name in kwargs:
        return kwargs[name]
    if len(args) > position:
        return args[position]
    return None


def _assert_child_dependencies(
    control,
    repository,
    resolver,
    audit,
    events,
):
    assert len(control.initializations) == 1
    initialization = control.initializations[0]
    assert (
        _argument(initialization, "job_repository", 0)
        is repository
    )
    if control.uses_resolver:
        assert (
            _argument(initialization, "provider_resolver", 1)
            is resolver
        )
        observer_offset = 2
    else:
        observer_offset = 1
    assert _argument(initialization, "audit", observer_offset) is audit
    assert (
        _argument(initialization, "events", observer_offset + 1)
        is events
    )


def _assert_only_child_called(controls, selected, task_id=TASK_ID):
    for symbol, control in controls.items():
        if symbol == selected:
            assert control.calls == [str(task_id)]
        else:
            assert control.calls == []


def _assert_no_child_called(controls):
    assert all(not control.calls for control in controls.values())


def _route_setup(monkeypatch, action, status, retrieved, finalized):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(
        terminal_status=status,
        retrieved=retrieved,
        finalized=finalized,
    )
    resolver = ResolverBomb()
    audit = ObserverBomb()
    events = ObserverBomb()
    coordinator = _make_coordinator(
        module,
        repository,
        resolver,
        audit,
        events,
    )
    selected = ACTION_CHILD[action]
    return (
        module,
        controls,
        repository,
        resolver,
        audit,
        events,
        coordinator,
        selected,
    )


@pytest.mark.parametrize(
    "action,status,retrieved,finalized",
    VALID_ROUTES,
)
def test_valid_topology_routes_to_exactly_one_child(
    monkeypatch,
    action,
    status,
    retrieved,
    finalized,
):
    (
        _,
        controls,
        repository,
        resolver,
        audit,
        events,
        coordinator,
        selected,
    ) = _route_setup(
        monkeypatch,
        action,
        status,
        retrieved,
        finalized,
    )
    child_result = controls[selected].result

    returned = coordinator.advance_once(TASK_ID)

    assert set(returned) == {"task_id", "action", "result"}
    assert returned["task_id"] == TASK_ID
    assert returned["action"] == action
    assert returned["result"] is child_result
    _assert_only_child_called(controls, selected)
    _assert_child_dependencies(
        controls[selected],
        repository,
        resolver,
        audit,
        events,
    )
    assert resolver.calls == 0
    assert audit.calls == 0
    assert events.calls == 0


@pytest.mark.parametrize(
    "child_result",
    (
        {"status": "running"},
        {"status": "succeeded"},
        {"status": "failed"},
        {"status": "cancelled"},
    ),
)
def test_poll_result_never_falls_through_to_another_child(
    monkeypatch,
    child_result,
):
    (
        _,
        controls,
        _,
        _,
        _,
        _,
        coordinator,
        selected,
    ) = _route_setup(
        monkeypatch,
        "poll",
        None,
        False,
        False,
    )
    controls[selected].result = child_result

    returned = coordinator.advance_once(TASK_ID)

    assert returned["result"] is child_result
    _assert_only_child_called(controls, selected)


@pytest.mark.parametrize(
    "action,status,retrieved,finalized,child_result",
    (
        (
            "retrieve",
            "succeeded",
            False,
            False,
            {"result_state": "retrieved"},
        ),
        (
            "finalize",
            "succeeded",
            True,
            False,
            {"result_state": "finalized", "asset_ready": True},
        ),
        (
            "reconcile_terminal",
            "failed",
            False,
            False,
            {"status": "failed"},
        ),
        (
            "reconcile_success",
            "succeeded",
            True,
            True,
            {"status": "done"},
        ),
    ),
)
def test_selected_child_result_never_causes_fall_through(
    monkeypatch,
    action,
    status,
    retrieved,
    finalized,
    child_result,
):
    (
        _,
        controls,
        _,
        _,
        _,
        _,
        coordinator,
        selected,
    ) = _route_setup(
        monkeypatch,
        action,
        status,
        retrieved,
        finalized,
    )
    controls[selected].result = child_result

    returned = coordinator.advance_once(TASK_ID)

    assert returned["result"] is child_result
    _assert_only_child_called(controls, selected)


@pytest.mark.parametrize(
    "status,retrieved,finalized",
    INVALID_TOPOLOGIES,
)
def test_invalid_topology_calls_no_child(
    monkeypatch,
    status,
    retrieved,
    finalized,
):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(
        terminal_status=status,
        retrieved=retrieved,
        finalized=finalized,
    )
    resolver = ResolverBomb()
    audit = ObserverBomb()
    events = ObserverBomb()
    coordinator = _make_coordinator(
        module,
        repository,
        resolver,
        audit,
        events,
    )

    with pytest.raises(module.GenerationLifecycleCoordinatorError):
        coordinator.advance_once(TASK_ID)

    _assert_no_child_called(controls)
    assert resolver.calls == 0
    assert audit.calls == 0
    assert events.calls == 0


@pytest.mark.parametrize(
    "repository_error",
    (
        GenerationJobRepositoryError("missing submitted receipt"),
        GenerationJobReceiptError("corrupt submitted receipt"),
    ),
    ids=("missing", "malformed"),
)
def test_submitted_repository_error_is_chained_and_calls_no_child(
    monkeypatch,
    repository_error,
):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository()
    repository.effects["resume"] = repository_error
    coordinator = _make_coordinator(
        module,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(
        module.GenerationLifecycleCoordinatorError
    ) as exc_info:
        coordinator.advance_once(TASK_ID)

    assert exc_info.value.__cause__ is repository_error
    _assert_no_child_called(controls)


def test_requested_task_identity_mismatch_calls_no_child(monkeypatch):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(submitted=_submitted("other-task"))
    coordinator = _make_coordinator(
        module,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationLifecycleCoordinatorError):
        coordinator.advance_once(TASK_ID)

    _assert_no_child_called(controls)
    assert [name for name, _ in repository.calls] == ["resume"]


def test_malformed_terminal_error_is_chained_and_calls_no_child(
    monkeypatch,
):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(terminal_status="succeeded")
    original = GenerationJobTerminalError("corrupt terminal")
    repository.effects["load_terminal"] = original
    coordinator = _make_coordinator(
        module,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(
        module.GenerationLifecycleCoordinatorError
    ) as exc_info:
        coordinator.advance_once(TASK_ID)

    assert exc_info.value.__cause__ is original
    _assert_no_child_called(controls)


def test_unknown_terminal_status_calls_no_child(monkeypatch):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(terminal_status="mystery")
    coordinator = _make_coordinator(
        module,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationLifecycleCoordinatorError):
        coordinator.advance_once(TASK_ID)

    _assert_no_child_called(controls)


def test_terminal_requested_task_identity_mismatch_calls_no_child(
    monkeypatch,
):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(terminal_status="succeeded")
    repository.terminal["task_id"] = "other-task"
    coordinator = _make_coordinator(
        module,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationLifecycleCoordinatorError):
        coordinator.advance_once(TASK_ID)

    _assert_no_child_called(controls)


@pytest.mark.parametrize(
    "field,replacement",
    (
        ("task_id", "other-task"),
        ("task_type", "image"),
        ("job_id", "other-job"),
        ("provider", "other-provider"),
        ("metadata", {"scene_id": 9, "shot_id": 2}),
    ),
)
def test_submitted_terminal_identity_mismatch_calls_no_child(
    monkeypatch,
    field,
    replacement,
):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(terminal_status="succeeded")
    repository.terminal[field] = replacement
    coordinator = _make_coordinator(
        module,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(module.GenerationLifecycleCoordinatorError):
        coordinator.advance_once(TASK_ID)

    _assert_no_child_called(controls)


@pytest.mark.parametrize(
    "action,status,retrieved,finalized,error_type",
    (
        (
            "poll",
            None,
            False,
            False,
            GenerationJobLifecycleError,
        ),
        (
            "retrieve",
            "succeeded",
            False,
            False,
            GenerationJobResultLifecycleError,
        ),
        (
            "finalize",
            "succeeded",
            True,
            False,
            GenerationJobAssetLifecycleError,
        ),
        (
            "reconcile_success",
            "succeeded",
            True,
            True,
            GenerationResultReconciliationError,
        ),
        (
            "reconcile_terminal",
            "failed",
            False,
            False,
            GenerationTerminalReconciliationError,
        ),
    ),
)
def test_known_child_error_is_normalized_with_exact_cause(
    monkeypatch,
    action,
    status,
    retrieved,
    finalized,
    error_type,
):
    (
        module,
        controls,
        _,
        _,
        _,
        _,
        coordinator,
        selected,
    ) = _route_setup(
        monkeypatch,
        action,
        status,
        retrieved,
        finalized,
    )
    original = error_type("known child failure")
    controls[selected].error = original

    with pytest.raises(
        module.GenerationLifecycleCoordinatorError
    ) as exc_info:
        coordinator.advance_once(TASK_ID)

    assert exc_info.value.__cause__ is original
    _assert_only_child_called(controls, selected)


@pytest.mark.parametrize(
    "action,status,retrieved,finalized",
    VALID_ROUTES,
)
def test_programming_exception_from_child_is_not_normalized(
    monkeypatch,
    action,
    status,
    retrieved,
    finalized,
):
    (
        module,
        controls,
        _,
        _,
        _,
        _,
        coordinator,
        selected,
    ) = _route_setup(
        monkeypatch,
        action,
        status,
        retrieved,
        finalized,
    )
    original = ValueError("programming defect")
    controls[selected].error = original

    with pytest.raises(ValueError) as exc_info:
        coordinator.advance_once(TASK_ID)

    assert exc_info.value is original
    assert not isinstance(
        exc_info.value,
        module.GenerationLifecycleCoordinatorError,
    )
    _assert_only_child_called(controls, selected)


def test_programming_exception_from_repository_is_not_normalized(
    monkeypatch,
):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository()
    original = ValueError("repository test-double defect")
    repository.effects["terminal_exists"] = original
    coordinator = _make_coordinator(
        module,
        repository,
        ResolverBomb(),
        ObserverBomb(),
        ObserverBomb(),
    )

    with pytest.raises(ValueError) as exc_info:
        coordinator.advance_once(TASK_ID)

    assert exc_info.value is original
    _assert_no_child_called(controls)


def test_non_string_requested_task_id_uses_its_string_form(monkeypatch):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository(submitted=_submitted(7))
    resolver = ResolverBomb()
    coordinator = _make_coordinator(
        module,
        repository,
        resolver,
        None,
        None,
        include_observers=False,
    )

    returned = coordinator.advance_once(7)

    assert returned["task_id"] == "7"
    assert returned["action"] == "poll"
    _assert_only_child_called(
        controls,
        "GenerationJobLifecycle",
        task_id=7,
    )
    _assert_child_dependencies(
        controls["GenerationJobLifecycle"],
        repository,
        resolver,
        None,
        None,
    )


def test_public_constructor_requires_no_observers(monkeypatch):
    module = _load_future_module()
    controls = _install_child_spies(monkeypatch, module)
    repository = FakeRepository()
    resolver = ResolverBomb()

    coordinator = module.GenerationLifecycleCoordinator(
        repository,
        resolver,
    )
    returned = coordinator.advance_once(TASK_ID)

    assert returned["action"] == "poll"
    _assert_child_dependencies(
        controls["GenerationJobLifecycle"],
        repository,
        resolver,
        None,
        None,
    )


@pytest.mark.parametrize(
    "action,status,retrieved,finalized",
    (
        ("reconcile_success", "succeeded", True, True),
        ("reconcile_terminal", "failed", False, False),
        ("reconcile_terminal", "cancelled", False, False),
    ),
)
def test_repeated_calls_route_once_per_call_without_coordinator_cache(
    monkeypatch,
    action,
    status,
    retrieved,
    finalized,
):
    (
        _,
        controls,
        _,
        _,
        _,
        _,
        coordinator,
        selected,
    ) = _route_setup(
        monkeypatch,
        action,
        status,
        retrieved,
        finalized,
    )
    child_result = controls[selected].result

    first = coordinator.advance_once(TASK_ID)
    second = coordinator.advance_once(TASK_ID)

    assert first["result"] is child_result
    assert second["result"] is child_result
    assert controls[selected].calls == [TASK_ID, TASK_ID]
    assert sum(len(item.calls) for item in controls.values()) == 2


def test_coordinator_has_no_batch_loop_or_forbidden_orchestrator_reference():
    module = _load_future_module()
    source = inspect.getsource(module)
    tree = ast.parse(source)

    assert not any(
        isinstance(node, (ast.For, ast.AsyncFor, ast.While))
        for node in ast.walk(tree)
    )
    for forbidden_symbol in (
        "GenerationQueue",
        "GenerationEngine",
        "MoviePipeline",
    ):
        assert forbidden_symbol not in source
