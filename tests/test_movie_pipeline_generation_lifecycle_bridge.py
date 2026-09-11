import ast
import inspect
import json
from pathlib import Path
import socket
import textwrap
from types import SimpleNamespace

import pytest

import core.ai_core.providers.auth.credential_manager as credential_module
import core.movie_engine.movie_pipeline as movie_pipeline_module
from core.ai_core.generation_job_lifecycle import GenerationJobLifecycleError
from core.ai_core.generation_job_repository import GenerationJobRepository
from core.ai_core.generation_queue import GenerationTask
from core.ai_core.providers.auth.credential_manager import CredentialManager
from core.movie_engine.generation_engine import GenerationEngine
from core.movie_engine.generation_lifecycle_coordinator import (
    GenerationLifecycleCoordinatorError,
)
from core.movie_engine.generation_scene_lifecycle import (
    GenerationSceneLifecycleError,
)
from core.movie_engine.movie_pipeline import MoviePipeline


SCENE_ID = 7
TASK_ID = "stage2s-task-001"
JOB_ID = "stage2s-job-001"
EXACT_PROVIDER = "stage2s-exact-remote-provider"


class SceneIdentitySentinel:
    def _reject(self, operation):
        raise AssertionError(f"Stage 2S must not {operation} scene_id")

    def __int__(self):
        self._reject("convert")

    def __index__(self):
        self._reject("index")

    def __str__(self):
        self._reject("stringify")

    def __format__(self, _format_spec):
        self._reject("format")

    def __copy__(self):
        self._reject("copy")

    def __deepcopy__(self, _memo):
        self._reject("deep-copy")


class CustomProgrammingError(RuntimeError):
    pass


class StatusProvider:
    def __init__(self, name, response=None):
        self.name = name
        self.response = response
        self.calls = []

    def get_status(self, job_id):
        self.calls.append(job_id)
        if self.response is None:
            raise AssertionError("mismatched provider must not be called")
        return dict(self.response)


class ExactProviderResolver:
    """Reference implementation used only to validate the durable fixture."""

    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def get(self, name):
        self.calls.append(name)
        if getattr(self.provider, "name", None) == name:
            return self.provider
        return None


class QueueBomb:
    def __getattr__(self, name):
        raise AssertionError(f"Stage 2S must not access a queue via {name}")


class EngineInstanceSpy:
    def __init__(self, inspect_effect, advance_effect):
        self.inspect_effect = inspect_effect
        self.advance_effect = advance_effect
        self.inspect_calls = []
        self.advance_calls = []
        self.provider_manager = object()

    @staticmethod
    def _apply(effect):
        if isinstance(effect, BaseException):
            raise effect
        return effect

    def inspect_scene_lifecycle(self, scene_id):
        self.inspect_calls.append(scene_id)
        return self._apply(self.inspect_effect)

    def advance_scene_once(self, scene_id):
        self.advance_calls.append(scene_id)
        return self._apply(self.advance_effect)


class EngineFactorySpy:
    def __init__(self, effects):
        self.effects = list(effects)
        self.calls = []
        self.instances = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        inspect_effect, advance_effect = self.effects[len(self.instances)]
        instance = EngineInstanceSpy(inspect_effect, advance_effect)
        self.instances.append(instance)
        return instance


def _future_method(pipeline, method_name):
    method = getattr(pipeline, method_name, None)
    assert callable(method), (
        f"Stage 2S RED: MoviePipeline.{method_name} is missing"
    )
    return method


def _call_future(pipeline, method_name, scene_id):
    return _future_method(pipeline, method_name)(scene_id)


def _make_pipeline(project_path, provider, **overrides):
    dependencies = {
        "ai_director": object(),
        "scene_builder": object(),
        "generation_queue": QueueBomb(),
        "video_provider": provider,
        "production_orchestrator": object(),
        "reactive_orchestrator": object(),
    }
    dependencies.update(overrides)
    return MoviePipeline(project_path=project_path, **dependencies)


def _snapshot_state(pipeline):
    return {
        "keys": tuple(pipeline.__dict__),
        "identities": {
            name: id(value)
            for name, value in pipeline.__dict__.items()
        },
    }


def _snapshot_files(project_path):
    return {
        str(path.relative_to(project_path)): path.read_bytes()
        for path in sorted(project_path.rglob("*"))
        if path.is_file()
    }


def _write_durable_running_scene(project_path, provider_name):
    repository = GenerationJobRepository(project_path)
    task = GenerationTask(
        task_type="video",
        prompt="Stage 2S durable lifecycle bridge",
        provider=SimpleNamespace(name=provider_name),
        project_path=project_path,
        metadata={"scene_id": SCENE_ID, "shot_id": 3},
    )
    task.task_id = TASK_ID
    receipt = repository.persist(
        task,
        {
            "status": "submitted",
            "job_id": JOB_ID,
            "provider": provider_name,
        },
    )

    document = {
        "scene_id": SCENE_ID,
        "status": "pending",
        "tasks": [
            {
                "task_id": TASK_ID,
                "type": "video",
                "provider": provider_name,
                "status": "submitted",
                "metadata": {"scene_id": SCENE_ID, "shot_id": 3},
                "result": {
                    "status": "submitted",
                    "job_id": JOB_ID,
                    "provider": provider_name,
                },
                "output": None,
            }
        ],
    }
    scene_path = (
        project_path
        / "render_output"
        / f"scene_{SCENE_ID:03d}"
        / "generation_result.json"
    )
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    scene_path.write_text(
        json.dumps(document, indent=2),
        encoding="utf-8",
    )
    return repository, receipt, scene_path


def _running_provider(name):
    return StatusProvider(
        name,
        {
            "status": "running",
            "job_id": JOB_ID,
            "provider": name,
        },
    )


def _assert_no_later_durable_state(project_path):
    assert not (
        project_path / "generation_jobs" / "terminal" / f"{TASK_ID}.json"
    ).exists()
    assert not (
        project_path / "generation_jobs" / "retrieved" / f"{TASK_ID}.json"
    ).exists()
    assert not (
        project_path / "generation_jobs" / "finalized" / f"{TASK_ID}.json"
    ).exists()
    assert not (project_path / "assets" / "registry.json").exists()


def _install_engine_factory(monkeypatch, effects):
    factory = EngineFactorySpy(effects)
    monkeypatch.setattr(
        movie_pipeline_module,
        "GenerationEngine",
        factory,
        raising=False,
    )
    return factory


def _method_ast(method_name):
    method = getattr(MoviePipeline, method_name, None)
    assert callable(method), (
        f"Stage 2S RED: MoviePipeline.{method_name} is missing"
    )
    function = ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]
    assert isinstance(function, ast.FunctionDef)
    return function


def test_movie_pipeline_exposes_both_explicit_lifecycle_bridges():
    assert callable(
        getattr(MoviePipeline, "inspect_scene_lifecycle", None)
    ), "Stage 2S RED: MoviePipeline.inspect_scene_lifecycle is missing"
    assert callable(
        getattr(MoviePipeline, "advance_scene_once", None)
    ), "Stage 2S RED: MoviePipeline.advance_scene_once is missing"


def test_movie_pipeline_exposes_canonical_generation_engine_symbol():
    assert getattr(movie_pipeline_module, "GenerationEngine", None) is GenerationEngine, (
        "Stage 2S RED: movie_pipeline.GenerationEngine module symbol is missing"
    )


@pytest.mark.parametrize(
    ("method_name", "matching_calls", "other_calls", "effects"),
    [
        (
            "inspect_scene_lifecycle",
            "inspect_calls",
            "advance_calls",
            ((object(), AssertionError("advance cross-call")),),
        ),
        (
            "advance_scene_once",
            "advance_calls",
            "inspect_calls",
            ((AssertionError("inspect cross-call"), object()),),
        ),
    ],
)
def test_bridge_constructs_one_engine_and_delegates_once_with_exact_identity(
    monkeypatch,
    method_name,
    matching_calls,
    other_calls,
    effects,
):
    project_path = object()
    provider = SimpleNamespace(name=EXACT_PROVIDER)
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.project_path = project_path
    pipeline.video_provider = provider
    pipeline.generation_queue = QueueBomb()
    scene_id = SceneIdentitySentinel()
    factory = _install_engine_factory(monkeypatch, effects)
    child_result = effects[0][0 if method_name.startswith("inspect") else 1]

    actual = _call_future(pipeline, method_name, scene_id)

    assert len(factory.calls) == 1
    args, kwargs = factory.calls[0]
    assert args == ()
    assert list(kwargs) == ["project_path"]
    assert kwargs["project_path"] is project_path
    engine = factory.instances[0]
    calls = getattr(engine, matching_calls)
    assert len(calls) == 1
    assert calls[0] is scene_id
    assert getattr(engine, other_calls) == []
    assert actual is child_result

    resolver = engine.provider_manager
    assert resolver.get(EXACT_PROVIDER) is provider
    assert resolver.get(EXACT_PROVIDER.upper()) is None
    assert resolver.get(f"{EXACT_PROVIDER}-other") is None


@pytest.mark.parametrize(
    "error",
    [
        GenerationSceneLifecycleError("stage 2q failure"),
        ValueError("programming value failure"),
        TypeError("programming type failure"),
        CustomProgrammingError("programming runtime failure"),
    ],
)
@pytest.mark.parametrize(
    ("method_name", "effect_index"),
    [
        ("inspect_scene_lifecycle", 0),
        ("advance_scene_once", 1),
    ],
)
def test_bridge_preserves_exact_child_exception(
    monkeypatch,
    method_name,
    effect_index,
    error,
):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.project_path = object()
    pipeline.video_provider = SimpleNamespace(name=EXACT_PROVIDER)
    effects = [object(), object()]
    effects[effect_index] = error
    _install_engine_factory(monkeypatch, [tuple(effects)])

    with pytest.raises(type(error)) as exc_info:
        _call_future(pipeline, method_name, object())

    assert exc_info.value is error


@pytest.mark.parametrize(
    "method_name",
    ["inspect_scene_lifecycle", "advance_scene_once"],
)
def test_bridge_uses_fresh_engine_and_does_not_mutate_pipeline_state(
    monkeypatch,
    method_name,
):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.project_path = object()
    pipeline.ai_director = object()
    pipeline.scene_builder = object()
    pipeline.generation_queue = QueueBomb()
    pipeline.video_provider = SimpleNamespace(name=EXACT_PROVIDER)
    pipeline.production_orchestrator = object()
    pipeline.reactive_orchestrator = object()
    pipeline._scene_inputs = {}
    first = object()
    second = object()
    effects = (
        [(first, object()), (second, object())]
        if method_name.startswith("inspect")
        else [(object(), first), (object(), second)]
    )
    factory = _install_engine_factory(monkeypatch, effects)
    before = _snapshot_state(pipeline)

    actual_first = _call_future(pipeline, method_name, object())
    actual_second = _call_future(pipeline, method_name, object())

    assert actual_first is first
    assert actual_second is second
    assert factory.instances[0] is not factory.instances[1]
    assert len(factory.calls) == 2
    assert _snapshot_state(pipeline) == before


def test_inspect_then_advance_use_distinct_engines_and_same_resolver_policy(
    monkeypatch,
):
    provider = SimpleNamespace(name=EXACT_PROVIDER)
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.project_path = object()
    pipeline.video_provider = provider
    inspected = object()
    advanced = object()
    factory = _install_engine_factory(
        monkeypatch,
        [(inspected, object()), (object(), advanced)],
    )

    assert _call_future(pipeline, "inspect_scene_lifecycle", object()) is inspected
    assert _call_future(pipeline, "advance_scene_once", object()) is advanced

    assert factory.instances[0] is not factory.instances[1]
    for engine in factory.instances:
        assert engine.provider_manager.get(EXACT_PROVIDER) is provider
        assert engine.provider_manager.get("Video AI") is None


def test_real_durable_fixture_reaches_stage2h_with_reference_exact_resolver(
    tmp_path,
):
    project_path = tmp_path / "reference-path"
    provider = _running_provider(EXACT_PROVIDER)
    repository, receipt, _scene_path = _write_durable_running_scene(
        project_path,
        EXACT_PROVIDER,
    )
    receipt_before = repository.receipt_path(TASK_ID).read_bytes()
    resolver = ExactProviderResolver(provider)
    engine = GenerationEngine(project_path=project_path)
    engine.provider_manager = resolver

    result = engine.advance_scene_once(SCENE_ID)

    assert result["advanced_count"] == 1
    assert result["advanced"][0]["action"] == "poll"
    assert result["advanced"][0]["result"] == {
        "status": "running",
        "job_id": JOB_ID,
        "provider": EXACT_PROVIDER,
    }
    assert resolver.calls == [EXACT_PROVIDER]
    assert provider.calls == [JOB_ID]
    assert repository.receipt_path(TASK_ID).read_bytes() == receipt_before
    _assert_no_later_durable_state(project_path)


def test_real_movie_pipeline_advance_reaches_exact_configured_provider_once(
    monkeypatch,
    tmp_path,
):
    project_path = tmp_path / "success"
    provider = _running_provider(EXACT_PROVIDER)
    repository, receipt, _scene_path = _write_durable_running_scene(
        project_path,
        EXACT_PROVIDER,
    )
    receipt_path = repository.receipt_path(TASK_ID)
    receipt_before = receipt_path.read_bytes()
    files_before = _snapshot_files(project_path)
    pipeline = _make_pipeline(project_path, provider)
    state_before = _snapshot_state(pipeline)

    def secret_bomb(*_args, **_kwargs):
        raise AssertionError("Stage 2S bridge must not read credentials")

    monkeypatch.setattr(CredentialManager, "get_key", secret_bomb)
    monkeypatch.setattr(CredentialManager, "has_key", secret_bomb)
    monkeypatch.setattr(CredentialManager, "list_configured", secret_bomb)
    monkeypatch.setattr(credential_module.subprocess, "run", secret_bomb)
    monkeypatch.setattr(socket, "create_connection", secret_bomb)

    result = _call_future(pipeline, "advance_scene_once", SCENE_ID)

    assert receipt["provider"] == EXACT_PROVIDER
    assert pipeline.video_provider is provider
    assert provider.calls == [JOB_ID]
    assert result["scene_id"] == SCENE_ID
    assert result["advanced_count"] == 1
    assert result["advanced"][0]["task_id"] == TASK_ID
    assert result["advanced"][0]["action"] == "poll"
    assert result["advanced"][0]["result"]["job_id"] == JOB_ID
    assert result["advanced"][0]["result"]["provider"] == EXACT_PROVIDER
    assert receipt_path.read_bytes() == receipt_before
    assert _snapshot_files(project_path) == files_before
    assert _snapshot_state(pipeline) == state_before
    _assert_no_later_durable_state(project_path)


def test_real_movie_pipeline_rejects_provider_mismatch_without_fallback(
    tmp_path,
):
    project_path = tmp_path / "mismatch"
    required_provider = "stage2s-required-provider"
    configured = StatusProvider("stage2s-other-provider")
    repository, receipt, _scene_path = _write_durable_running_scene(
        project_path,
        required_provider,
    )
    receipt_path = repository.receipt_path(TASK_ID)
    receipt_before = receipt_path.read_bytes()
    files_before = _snapshot_files(project_path)
    pipeline = _make_pipeline(project_path, configured)

    with pytest.raises(GenerationSceneLifecycleError) as exc_info:
        _call_future(pipeline, "advance_scene_once", SCENE_ID)

    coordinator_error = exc_info.value.__cause__
    assert isinstance(coordinator_error, GenerationLifecycleCoordinatorError)
    lifecycle_error = coordinator_error.__cause__
    assert isinstance(lifecycle_error, GenerationJobLifecycleError)
    assert required_provider in str(lifecycle_error)
    assert "unavailable" in str(lifecycle_error)
    assert receipt["provider"] == required_provider
    assert configured.calls == []
    assert receipt_path.read_bytes() == receipt_before
    assert _snapshot_files(project_path) == files_before
    _assert_no_later_durable_state(project_path)


def test_real_movie_pipeline_inspection_is_read_only_and_never_polls_provider(
    tmp_path,
):
    project_path = tmp_path / "inspection"
    provider = _running_provider(EXACT_PROVIDER)
    _repository, _receipt, _scene_path = _write_durable_running_scene(
        project_path,
        EXACT_PROVIDER,
    )
    pipeline = _make_pipeline(project_path, provider)
    files_before = _snapshot_files(project_path)
    state_before = _snapshot_state(pipeline)

    result = _call_future(pipeline, "inspect_scene_lifecycle", SCENE_ID)

    assert result == {
        "scene_id": SCENE_ID,
        "active_count": 1,
        "needs_advance": True,
        "plan": [{"task_id": TASK_ID, "action": "poll"}],
    }
    assert provider.calls == []
    assert _snapshot_files(project_path) == files_before
    assert _snapshot_state(pipeline) == state_before
    _assert_no_later_durable_state(project_path)


def test_constructor_signature_stays_compatible_and_engine_is_not_eager(
    monkeypatch,
    tmp_path,
):
    expected_parameters = (
        "self",
        "project_path",
        "ai_director",
        "scene_builder",
        "generation_queue",
        "video_provider",
        "production_orchestrator",
        "reactive_orchestrator",
    )
    assert tuple(inspect.signature(MoviePipeline.__init__).parameters) == (
        expected_parameters
    )

    class ConstructionBomb:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("MoviePipeline.__init__ must not create an engine")

    monkeypatch.setattr(
        movie_pipeline_module,
        "GenerationEngine",
        ConstructionBomb,
        raising=False,
    )
    _make_pipeline(
        tmp_path,
        SimpleNamespace(name=EXACT_PROVIDER),
    )


def test_legacy_scene_and_regeneration_methods_do_not_auto_continue():
    forbidden = {
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "GenerationEngine",
    }
    for method_name in (
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
    ):
        method = getattr(MoviePipeline, method_name)
        source_tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
        names = {
            node.id
            for node in ast.walk(source_tree)
            if isinstance(node, ast.Name)
        } | {
            node.attr
            for node in ast.walk(source_tree)
            if isinstance(node, ast.Attribute)
        }
        assert names.isdisjoint(forbidden), (
            f"legacy {method_name} must not auto-run Stage 2S lifecycle bridges"
        )


@pytest.mark.parametrize(
    ("method_name", "matching_child", "forbidden_child"),
    [
        (
            "inspect_scene_lifecycle",
            "inspect_scene_lifecycle",
            "advance_scene_once",
        ),
        (
            "advance_scene_once",
            "advance_scene_once",
            "inspect_scene_lifecycle",
        ),
    ],
)
def test_future_bridge_ast_is_bounded_delegation_only(
    method_name,
    matching_child,
    forbidden_child,
):
    function = _method_ast(method_name)
    nodes = list(ast.walk(function))

    assert not any(
        isinstance(
            node,
            (
                ast.For,
                ast.While,
                ast.Try,
                ast.AsyncFunctionDef,
                ast.Await,
                ast.Yield,
                ast.YieldFrom,
            ),
        )
        for node in nodes
    )
    assert not any(
        isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        and any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            for target in (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
        )
        for node in nodes
    )

    calls = [
        node.func.attr
        for node in nodes
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]
    assert calls.count(matching_child) == 1
    assert forbidden_child not in calls
    assert "generate_scene" not in calls
    assert set(calls).isdisjoint(
        {
            "process_all",
            "add_task",
            "resume",
            "terminal_exists",
            "load_terminal",
            "retrieved_exists",
            "finalized_exists",
            "read_text",
            "write_text",
            "mkdir",
            "sleep",
        }
    )


def test_movie_pipeline_source_owns_no_direct_durable_lifecycle_stage():
    source_tree = ast.parse(inspect.getsource(movie_pipeline_module))
    forbidden_names = {
        "GenerationSceneLifecycle",
        "GenerationLifecycleCoordinator",
        "GenerationJobLifecycle",
        "GenerationJobResultLifecycle",
        "GenerationJobAssetLifecycle",
        "GenerationResultReconciler",
        "GenerationTerminalReconciler",
        "GenerationJobRepository",
    }
    imported_or_used = {
        node.id
        for node in ast.walk(source_tree)
        if isinstance(node, ast.Name)
    } | {
        alias.name
        for node in ast.walk(source_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported_or_used.isdisjoint(forbidden_names)
