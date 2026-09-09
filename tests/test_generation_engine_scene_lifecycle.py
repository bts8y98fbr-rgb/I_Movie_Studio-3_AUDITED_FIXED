import ast
import inspect
import os
import subprocess
import sys
import textwrap

import pytest

import core.movie_engine.generation_engine as generation_engine_module
from core.movie_engine.generation_engine import GenerationEngine
from core.movie_engine.generation_scene_lifecycle import (
    GenerationSceneLifecycleError,
)


class SceneIdentitySentinel:
    def _reject(self, operation):
        raise AssertionError(f"scene_id must not be {operation} by Stage 2P")

    def __int__(self):
        self._reject("converted to int")

    def __index__(self):
        self._reject("used as an integer index")

    def __str__(self):
        self._reject("converted to str")

    def __format__(self, _format_spec):
        self._reject("formatted")

    def __copy__(self):
        self._reject("copied")

    def __deepcopy__(self, _memo):
        self._reject("deep-copied")


class ResolverBomb:
    def get(self, *_args, **_kwargs):
        raise AssertionError("Stage 2P must not resolve providers directly")


class QueueBomb:
    def __getattr__(self, name):
        raise AssertionError(f"Stage 2P must not access Queue.{name}")


class RepositoryBomb:
    def __init__(self, *_args, **_kwargs):
        raise AssertionError("Stage 2P must not construct a repository")


class LifecycleInstanceSpy:
    def __init__(self, effect):
        self.effect = effect
        self.advance_calls = []

    def advance_once(self, scene_id):
        self.advance_calls.append(scene_id)
        if isinstance(self.effect, BaseException):
            raise self.effect
        return self.effect


class LifecycleFactorySpy:
    def __init__(self, effects):
        self.effects = list(effects)
        self.constructor_calls = []
        self.instances = []

    def __call__(self, *args, **kwargs):
        self.constructor_calls.append((args, kwargs))
        effect = self.effects[len(self.instances)]
        instance = LifecycleInstanceSpy(effect)
        self.instances.append(instance)
        return instance


class CustomProgrammingError(RuntimeError):
    pass


def make_bare_engine():
    engine = GenerationEngine.__new__(GenerationEngine)
    engine.project_path = object()
    engine.provider_manager = ResolverBomb()
    engine.queue = QueueBomb()
    engine.model_policy = object()
    return engine


def install_lifecycle_factory(monkeypatch, *effects):
    factory = LifecycleFactorySpy(effects)
    monkeypatch.setattr(
        generation_engine_module,
        "GenerationSceneLifecycle",
        factory,
        raising=False,
    )
    return factory


def call_future_bridge(engine, scene_id):
    method = getattr(engine, "advance_scene_once", None)
    assert callable(method), (
        "Stage 2P RED: GenerationEngine.advance_scene_once is missing"
    )
    return method(scene_id)


def future_bridge_ast():
    method = getattr(GenerationEngine, "advance_scene_once", None)
    assert callable(method), (
        "Stage 2P RED: GenerationEngine.advance_scene_once is missing"
    )
    source = textwrap.dedent(inspect.getsource(method))
    function = ast.parse(source).body[0]
    assert isinstance(function, ast.FunctionDef)
    return function


def snapshot_engine_state(engine):
    return {
        "keys": tuple(engine.__dict__),
        "identities": {
            name: id(value)
            for name, value in engine.__dict__.items()
        },
    }


def fail_if_called(name):
    def bomb(*_args, **_kwargs):
        raise AssertionError(f"Stage 2P must not call {name}")

    return bomb


def test_generation_engine_exposes_advance_scene_once():
    assert callable(getattr(GenerationEngine, "advance_scene_once", None)), (
        "Stage 2P RED: GenerationEngine.advance_scene_once is missing"
    )


def test_generation_engine_exposes_module_level_scene_lifecycle_symbol():
    assert hasattr(generation_engine_module, "GenerationSceneLifecycle"), (
        "Stage 2P RED: generation_engine.GenerationSceneLifecycle is missing"
    )


def test_bridge_delegates_once_with_exact_dependencies_scene_and_result(
    monkeypatch,
):
    engine = make_bare_engine()
    scene_id = SceneIdentitySentinel()
    child_result = object()
    factory = install_lifecycle_factory(monkeypatch, child_result)

    actual = call_future_bridge(engine, scene_id)

    assert len(factory.constructor_calls) == 1
    args, kwargs = factory.constructor_calls[0]
    assert args == ()
    assert set(kwargs) == {"project_path", "provider_resolver"}
    assert kwargs["project_path"] is engine.project_path
    assert kwargs["provider_resolver"] is engine.provider_manager
    assert len(factory.instances) == 1
    assert factory.instances[0].advance_calls == [scene_id]
    assert factory.instances[0].advance_calls[0] is scene_id
    assert actual is child_result


@pytest.mark.parametrize(
    "error",
    [
        GenerationSceneLifecycleError("stage 2o failure"),
        ValueError("programming value failure"),
        TypeError("programming type failure"),
        CustomProgrammingError("custom programming failure"),
    ],
    ids=[
        "stage-2o-error",
        "value-error",
        "type-error",
        "custom-runtime-error",
    ],
)
def test_bridge_preserves_exact_exception_identity(monkeypatch, error):
    engine = make_bare_engine()
    factory = install_lifecycle_factory(monkeypatch, error)

    with pytest.raises(type(error)) as exc_info:
        call_future_bridge(engine, object())

    assert exc_info.value is error
    assert len(factory.constructor_calls) == 1
    assert len(factory.instances) == 1
    assert len(factory.instances[0].advance_calls) == 1


def test_bridge_owns_no_provider_queue_repository_or_engine_side_effects(
    monkeypatch,
):
    engine = make_bare_engine()
    engine.generate_scene = fail_if_called("generate_scene")
    engine.load_result = fail_if_called("load_result")
    factory = install_lifecycle_factory(monkeypatch, object())
    monkeypatch.setattr(
        generation_engine_module,
        "GenerationJobRepository",
        RepositoryBomb,
        raising=False,
    )
    monkeypatch.setattr(
        generation_engine_module,
        "GenerationQueue",
        fail_if_called("GenerationQueue constructor"),
    )
    before = snapshot_engine_state(engine)
    original_queue = engine.queue
    original_project_path = engine.project_path
    original_provider_manager = engine.provider_manager
    original_model_policy = engine.model_policy

    call_future_bridge(engine, object())

    assert snapshot_engine_state(engine) == before
    assert engine.queue is original_queue
    assert engine.project_path is original_project_path
    assert engine.provider_manager is original_provider_manager
    assert engine.model_policy is original_model_policy
    assert len(factory.constructor_calls) == 1


def test_repeated_calls_create_fresh_lifecycles_without_result_cache(
    monkeypatch,
):
    engine = make_bare_engine()
    scene_a = object()
    scene_b = object()
    result_a = object()
    result_b = object()
    factory = install_lifecycle_factory(monkeypatch, result_a, result_b)

    actual_a = call_future_bridge(engine, scene_a)
    actual_b = call_future_bridge(engine, scene_b)

    assert len(factory.instances) == 2
    assert factory.instances[0] is not factory.instances[1]
    assert factory.instances[0].advance_calls == [scene_a]
    assert factory.instances[1].advance_calls == [scene_b]
    assert actual_a is result_a
    assert actual_b is result_b
    assert actual_b is not actual_a


def test_bridge_ast_is_only_one_construction_and_one_delegation():
    function = future_bridge_ast()

    forbidden_control_flow = (
        ast.AsyncFor,
        ast.AsyncFunctionDef,
        ast.AsyncWith,
        ast.Await,
        ast.For,
        ast.If,
        ast.Match,
        ast.Try,
        ast.While,
        ast.With,
        ast.Yield,
        ast.YieldFrom,
    )
    assert not any(
        isinstance(node, forbidden_control_flow)
        for node in ast.walk(function)
        if node is not function
    )

    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
    lifecycle_calls = [
        call
        for call in calls
        if isinstance(call.func, ast.Name)
        and call.func.id == "GenerationSceneLifecycle"
    ]
    advance_calls = [
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and call.func.attr == "advance_once"
    ]
    assert len(calls) == 2
    assert len(lifecycle_calls) == 1
    assert len(advance_calls) == 1

    lifecycle_call = lifecycle_calls[0]
    assert lifecycle_call.args == []
    assert [keyword.arg for keyword in lifecycle_call.keywords] == [
        "project_path",
        "provider_resolver",
    ]
    assert isinstance(lifecycle_call.keywords[0].value, ast.Attribute)
    assert lifecycle_call.keywords[0].value.attr == "project_path"
    assert isinstance(lifecycle_call.keywords[1].value, ast.Attribute)
    assert lifecycle_call.keywords[1].value.attr == "provider_manager"

    advance_call = advance_calls[0]
    assert len(advance_call.args) == 1
    assert isinstance(advance_call.args[0], ast.Name)
    assert advance_call.args[0].id == "scene_id"
    assert advance_call.keywords == []

    forbidden_names = {
        "GenerationEngine",
        "GenerationJobRepository",
        "GenerationQueue",
        "MoviePipeline",
        "aggregate_generation_tasks",
        "backoff",
        "generate_scene",
        "get",
        "load_result",
        "open",
        "persist",
        "retry",
        "sleep",
    }
    referenced_names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
    }
    referenced_names.update(
        node.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Attribute)
    )
    assert not forbidden_names.intersection(referenced_names)


def test_bridge_ast_does_not_assign_engine_state():
    function = future_bridge_ast()

    assignment_targets = []
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assignment_targets.extend(targets)
        elif isinstance(node, ast.NamedExpr):
            assignment_targets.append(node.target)

    self_attributes = [
        nested
        for target in assignment_targets
        for nested in ast.walk(target)
        if isinstance(nested, ast.Attribute)
        and isinstance(nested.value, ast.Name)
        and nested.value.id == "self"
    ]
    assert self_attributes == []


def test_generate_scene_does_not_auto_continue_into_scene_lifecycle():
    source = textwrap.dedent(inspect.getsource(GenerationEngine.generate_scene))
    function = ast.parse(source).body[0]
    invoked_names = {
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }
    invoked_names.update(
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    )

    assert "advance_scene_once" not in invoked_names
    assert "GenerationSceneLifecycle" not in invoked_names


def test_fresh_interpreter_import_exposes_bridge_without_circular_import():
    command = (
        "import core.movie_engine.generation_engine as module\n"
        "assert hasattr(module, 'GenerationEngine')\n"
        "assert hasattr(module, 'GenerationSceneLifecycle'), "
        "'Stage 2P RED: module-level GenerationSceneLifecycle is missing'\n"
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [sys.executable, "-c", command],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
