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
        raise AssertionError(f"scene_id must not be {operation} by Stage 2R")

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


class DependencyBomb:
    def __getattr__(self, name):
        raise AssertionError(f"Stage 2R must not access dependency API {name}")


class ResolverBomb(DependencyBomb):
    def get(self, *_args, **_kwargs):
        raise AssertionError("Stage 2R must not resolve providers directly")


class QueueBomb(DependencyBomb):
    pass


class ConstructionBomb:
    def __init__(self, *_args, **_kwargs):
        raise AssertionError("Stage 2R must not construct this dependency")


class CustomProgrammingError(RuntimeError):
    pass


_FORBIDDEN_CALL = object()


def apply_effect(effect):
    if effect is _FORBIDDEN_CALL:
        raise AssertionError("Stage 2R called a forbidden lifecycle method")
    if isinstance(effect, BaseException):
        raise effect
    return effect


class LifecycleInstanceSpy:
    def __init__(self, inspect_effect, advance_effect=_FORBIDDEN_CALL):
        self.inspect_effect = inspect_effect
        self.advance_effect = advance_effect
        self.inspect_calls = []
        self.advance_calls = []

    def inspect(self, scene_id):
        self.inspect_calls.append(scene_id)
        return apply_effect(self.inspect_effect)

    def advance_once(self, scene_id):
        self.advance_calls.append(scene_id)
        return apply_effect(self.advance_effect)


class LifecycleFactorySpy:
    def __init__(self, specifications):
        self.specifications = list(specifications)
        self.constructor_calls = []
        self.instances = []

    def __call__(self, *args, **kwargs):
        self.constructor_calls.append((args, kwargs))
        specification = self.specifications[len(self.instances)]
        instance = LifecycleInstanceSpy(**specification)
        self.instances.append(instance)
        return instance


def make_bare_engine():
    engine = GenerationEngine.__new__(GenerationEngine)
    engine.project_path = object()
    engine.quality = object()
    engine.model_policy = object()
    engine.provider_manager = ResolverBomb()
    engine.provider_catalog = DependencyBomb()
    engine.provider_router = DependencyBomb()
    engine.credentials = DependencyBomb()
    engine.quality_policy = DependencyBomb()
    engine.queue = QueueBomb()
    return engine


def install_inspection_factory(monkeypatch, *effects):
    factory = LifecycleFactorySpy(
        [
            {
                "inspect_effect": effect,
                "advance_effect": _FORBIDDEN_CALL,
            }
            for effect in effects
        ]
    )
    monkeypatch.setattr(
        generation_engine_module,
        "GenerationSceneLifecycle",
        factory,
    )
    return factory


def call_future_inspection_bridge(engine, scene_id):
    method = getattr(engine, "inspect_scene_lifecycle", None)
    assert callable(method), (
        "Stage 2R RED: GenerationEngine.inspect_scene_lifecycle is missing"
    )
    return method(scene_id)


def future_inspection_bridge_ast():
    method = getattr(GenerationEngine, "inspect_scene_lifecycle", None)
    assert callable(method), (
        "Stage 2R RED: GenerationEngine.inspect_scene_lifecycle is missing"
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
        raise AssertionError(f"Stage 2R must not call {name}")

    return bomb


def test_generation_engine_exposes_inspect_scene_lifecycle():
    assert callable(
        getattr(GenerationEngine, "inspect_scene_lifecycle", None)
    ), "Stage 2R RED: GenerationEngine.inspect_scene_lifecycle is missing"


def test_generation_engine_retains_module_level_scene_lifecycle_symbol():
    assert hasattr(generation_engine_module, "GenerationSceneLifecycle")


def test_inspection_bridge_delegates_once_with_exact_identity_and_result(
    monkeypatch,
):
    engine = make_bare_engine()
    scene_id = SceneIdentitySentinel()
    child_result = object()
    factory = install_inspection_factory(monkeypatch, child_result)

    actual = call_future_inspection_bridge(engine, scene_id)

    assert len(factory.constructor_calls) == 1
    args, kwargs = factory.constructor_calls[0]
    assert args == ()
    assert list(kwargs) == ["project_path", "provider_resolver"]
    assert kwargs["project_path"] is engine.project_path
    assert kwargs["provider_resolver"] is engine.provider_manager
    assert len(factory.instances) == 1
    assert factory.instances[0].inspect_calls == [scene_id]
    assert factory.instances[0].inspect_calls[0] is scene_id
    assert factory.instances[0].advance_calls == []
    assert actual is child_result


@pytest.mark.parametrize(
    "error",
    [
        GenerationSceneLifecycleError("stage 2q failure"),
        ValueError("programming value failure"),
        TypeError("programming type failure"),
        CustomProgrammingError("custom programming failure"),
    ],
    ids=[
        "stage-2q-error",
        "value-error",
        "type-error",
        "custom-runtime-error",
    ],
)
def test_inspection_bridge_preserves_exact_exception_identity(
    monkeypatch,
    error,
):
    engine = make_bare_engine()
    factory = install_inspection_factory(monkeypatch, error)

    with pytest.raises(type(error)) as exc_info:
        call_future_inspection_bridge(engine, object())

    assert exc_info.value is error
    assert len(factory.constructor_calls) == 1
    assert len(factory.instances) == 1
    assert len(factory.instances[0].inspect_calls) == 1
    assert factory.instances[0].advance_calls == []


def test_inspection_bridge_owns_no_engine_dependency_or_state_side_effects(
    monkeypatch,
):
    engine = make_bare_engine()
    engine.advance_scene_once = fail_if_called("advance_scene_once")
    engine.generate_scene = fail_if_called("generate_scene")
    engine.load_result = fail_if_called("load_result")
    factory = install_inspection_factory(monkeypatch, object())

    for symbol in (
        "GenerationJobRepository",
        "GenerationQueue",
        "ProviderManager",
        "ProviderCatalog",
        "ProviderRouter",
        "CredentialManager",
        "QualityPolicy",
        "Path",
    ):
        monkeypatch.setattr(
            generation_engine_module,
            symbol,
            ConstructionBomb,
            raising=False,
        )

    before = snapshot_engine_state(engine)
    original_dependencies = {
        name: value
        for name, value in engine.__dict__.items()
    }

    call_future_inspection_bridge(engine, object())

    assert snapshot_engine_state(engine) == before
    assert all(
        getattr(engine, name) is value
        for name, value in original_dependencies.items()
    )
    assert len(factory.constructor_calls) == 1
    assert len(factory.instances[0].inspect_calls) == 1
    assert factory.instances[0].advance_calls == []


def test_repeated_inspection_calls_use_fresh_lifecycles_without_cache(
    monkeypatch,
):
    engine = make_bare_engine()
    scene_a = object()
    scene_b = object()
    result_a = object()
    result_b = object()
    factory = install_inspection_factory(monkeypatch, result_a, result_b)
    before = snapshot_engine_state(engine)

    actual_a = call_future_inspection_bridge(engine, scene_a)
    actual_b = call_future_inspection_bridge(engine, scene_b)

    assert len(factory.instances) == 2
    assert factory.instances[0] is not factory.instances[1]
    assert factory.instances[0].inspect_calls == [scene_a]
    assert factory.instances[1].inspect_calls == [scene_b]
    assert factory.instances[0].advance_calls == []
    assert factory.instances[1].advance_calls == []
    assert actual_a is result_a
    assert actual_b is result_b
    assert actual_b is not actual_a
    assert snapshot_engine_state(engine) == before


def test_inspection_bridge_ast_is_only_one_construction_and_inspection():
    function = future_inspection_bridge_ast()

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
    inspect_calls = [
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and call.func.attr == "inspect"
    ]
    assert len(calls) == 2
    assert len(lifecycle_calls) == 1
    assert len(inspect_calls) == 1

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

    inspect_call = inspect_calls[0]
    assert len(inspect_call.args) == 1
    assert isinstance(inspect_call.args[0], ast.Name)
    assert inspect_call.args[0].id == "scene_id"
    assert inspect_call.keywords == []

    forbidden_names = {
        "GenerationJobRepository",
        "GenerationQueue",
        "MoviePipeline",
        "Path",
        "add_task",
        "advance_scene_once",
        "backoff",
        "capabilities",
        "credentials",
        "finalized_exists",
        "generate_scene",
        "get",
        "get_result",
        "get_status",
        "json",
        "load_terminal",
        "load_result",
        "mkdir",
        "open",
        "persist",
        "process_all",
        "provider_catalog",
        "provider_router",
        "queue",
        "read_text",
        "resume",
        "retry",
        "select",
        "sleep",
        "submit",
        "terminal_exists",
        "retrieved_exists",
        "write_text",
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


def test_inspection_bridge_ast_does_not_assign_engine_state():
    function = future_inspection_bridge_ast()
    assignment_targets = []
    for node in ast.walk(function):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
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


@pytest.mark.parametrize(
    "method_name",
    ["generate_scene", "advance_scene_once"],
)
def test_existing_methods_do_not_auto_call_inspection(method_name):
    method = getattr(GenerationEngine, method_name)
    source = textwrap.dedent(inspect.getsource(method))
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
    assert "inspect_scene_lifecycle" not in invoked_names


def test_advance_scene_once_remains_exact_stage_2p_bridge(monkeypatch):
    engine = make_bare_engine()
    scene_id = SceneIdentitySentinel()
    advance_result = object()
    factory = LifecycleFactorySpy(
        [
            {
                "inspect_effect": _FORBIDDEN_CALL,
                "advance_effect": advance_result,
            }
        ]
    )
    monkeypatch.setattr(
        generation_engine_module,
        "GenerationSceneLifecycle",
        factory,
    )
    before = snapshot_engine_state(engine)

    actual = engine.advance_scene_once(scene_id)

    assert len(factory.constructor_calls) == 1
    args, kwargs = factory.constructor_calls[0]
    assert args == ()
    assert list(kwargs) == ["project_path", "provider_resolver"]
    assert kwargs["project_path"] is engine.project_path
    assert kwargs["provider_resolver"] is engine.provider_manager
    assert len(factory.instances) == 1
    assert factory.instances[0].advance_calls == [scene_id]
    assert factory.instances[0].advance_calls[0] is scene_id
    assert factory.instances[0].inspect_calls == []
    assert actual is advance_result
    assert snapshot_engine_state(engine) == before


def test_fresh_interpreter_import_retains_scene_lifecycle_symbol():
    command = (
        "import core.movie_engine.generation_engine as module\n"
        "assert hasattr(module, 'GenerationEngine')\n"
        "assert hasattr(module, 'GenerationSceneLifecycle')\n"
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
