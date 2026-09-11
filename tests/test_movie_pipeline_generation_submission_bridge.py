import ast
import inspect
import json
import textwrap
from types import SimpleNamespace

import pytest

import core.movie_engine.generation_engine as generation_engine_module
import core.movie_engine.movie_pipeline as movie_pipeline_module
from core.movie_engine.generation_engine import GenerationEngine
from core.movie_engine.movie_pipeline import MoviePipeline


SCENE_ID = 7
PROVIDER_NAME = "stage2t-exact-provider"


class SceneIdentitySentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2T MoviePipeline bridge must not {operation} scene_id"
        )

    def __int__(self):
        self._reject("convert")

    def __index__(self):
        self._reject("index")

    def __str__(self):
        self._reject("stringify")

    def __format__(self, _spec):
        self._reject("format")


class RecordingProvider:
    def __init__(self, name=PROVIDER_NAME, result_factory=None):
        self.name = name
        self.calls = []
        self.result_factory = result_factory

    def capabilities(self):
        return {
            "media_types": ["video"],
            "resolutions": [
                "1920x1080",
                "2048x1080",
                "3840x2160",
                "7680x4320",
            ],
            "fps": [24, 30, 60],
            "hdr": [False, True],
            "color_depth": [8, 10],
        }

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))

        if self.result_factory is not None:
            return self.result_factory(self, prompt, kwargs)

        return {
            "status": "generated",
            "provider": self.name,
            "marker": "stage2t-sync-result",
        }


class BombRouter:
    def select(self, *args, **kwargs):
        raise AssertionError(
            "explicit Stage 2T submission must not call ProviderRouter.select"
        )


class BombManager:
    def get(self, *args, **kwargs):
        raise AssertionError(
            "explicit Stage 2T submission must not call provider_manager.get"
        )


class EngineInstanceSpy:
    def __init__(self, effect):
        self.effect = effect
        self.calls = []
        self.inspect_calls = []
        self.advance_calls = []

    def submit_scene_generation(self, scene_id, provider):
        self.calls.append((scene_id, provider))
        if isinstance(self.effect, BaseException):
            raise self.effect
        return self.effect

    def inspect_scene_lifecycle(self, scene_id):
        self.inspect_calls.append(scene_id)
        raise AssertionError(
            "Stage 2T submission bridge must not inspect lifecycle"
        )

    def advance_scene_once(self, scene_id):
        self.advance_calls.append(scene_id)
        raise AssertionError(
            "Stage 2T submission bridge must not advance lifecycle"
        )


class EngineFactorySpy:
    def __init__(self, effects):
        self.effects = list(effects)
        self.calls = []
        self.instances = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        instance = EngineInstanceSpy(
            self.effects[len(self.instances)]
        )
        self.instances.append(instance)
        return instance


def _future_method(target, method_name):
    method = getattr(target, method_name, None)
    assert callable(method), (
        f"Stage 2T RED: {type(target).__name__}.{method_name} is missing"
        if not isinstance(target, type)
        else f"Stage 2T RED: {target.__name__}.{method_name} is missing"
    )
    return method


def _pipeline_without_constructor(project_path, provider):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.project_path = project_path
    pipeline.video_provider = provider
    return pipeline


def _install_engine_factory(monkeypatch, effects):
    factory = EngineFactorySpy(effects)
    monkeypatch.setattr(
        movie_pipeline_module,
        "GenerationEngine",
        factory,
    )
    return factory


def _write_render_plan(project_path, shot_count=1):
    scene_dir = (
        project_path
        / "render"
        / f"scene_{SCENE_ID:03d}"
    )
    scene_dir.mkdir(parents=True, exist_ok=True)

    shots = []
    for index in range(1, shot_count + 1):
        shots.append(
            {
                "shot_id": index,
                "director_prompt": f"Stage 2T shot {index}",
                "timeline": {
                    "duration": 2,
                },
                "quality": {
                    "resolution": "3840x2160",
                    "fps": 60,
                    "hdr": True,
                    "color_depth": 10,
                },
                "shot_model_selection": {
                    "selected_model": {
                        "name": "stage2t-model",
                    },
                },
            }
        )

    document = {
        "scene_id": SCENE_ID,
        "render_settings": {
            "resolution": "3840x2160",
            "fps": 60,
            "hdr": True,
            "color_depth": 10,
        },
        "shots": shots,
    }

    path = scene_dir / "render_plan.json"
    path.write_text(
        json.dumps(document, indent=2),
        encoding="utf-8",
    )
    return path


def _explicit_submit(engine, scene_id, provider):
    method = _future_method(
        engine,
        "submit_scene_generation",
    )
    return method(scene_id, provider=provider)


def test_stage2t_public_bridge_contracts_exist():
    assert callable(
        getattr(MoviePipeline, "submit_scene_generation", None)
    ), "Stage 2T RED: MoviePipeline.submit_scene_generation is missing"

    assert callable(
        getattr(GenerationEngine, "submit_scene_generation", None)
    ), "Stage 2T RED: GenerationEngine.submit_scene_generation is missing"


def test_movie_pipeline_bridge_uses_one_fresh_engine_exact_provider_and_scene_id(
    monkeypatch,
):
    project_path = object()
    provider = object()
    scene_id = SceneIdentitySentinel()
    result = object()

    pipeline = _pipeline_without_constructor(
        project_path,
        provider,
    )
    factory = _install_engine_factory(
        monkeypatch,
        [result],
    )

    actual = _future_method(
        pipeline,
        "submit_scene_generation",
    )(scene_id)

    assert actual is result
    assert len(factory.calls) == 1

    args, kwargs = factory.calls[0]
    assert args == ()
    assert kwargs == {
        "project_path": project_path,
    }

    engine = factory.instances[0]
    assert len(engine.calls) == 1

    actual_scene_id, actual_provider = engine.calls[0]
    assert actual_scene_id is scene_id
    assert actual_provider is provider
    assert engine.inspect_calls == []
    assert engine.advance_calls == []


def test_movie_pipeline_bridge_uses_fresh_engine_on_every_call(
    monkeypatch,
):
    provider = object()
    pipeline = _pipeline_without_constructor(
        object(),
        provider,
    )

    first_result = object()
    second_result = object()

    factory = _install_engine_factory(
        monkeypatch,
        [first_result, second_result],
    )

    method = _future_method(
        pipeline,
        "submit_scene_generation",
    )

    assert method(object()) is first_result
    assert method(object()) is second_result

    assert len(factory.instances) == 2
    assert factory.instances[0] is not factory.instances[1]

    assert factory.instances[0].calls[0][1] is provider
    assert factory.instances[1].calls[0][1] is provider


def test_movie_pipeline_bridge_preserves_exact_child_exception(
    monkeypatch,
):
    provider = object()
    pipeline = _pipeline_without_constructor(
        object(),
        provider,
    )

    error = RuntimeError(
        "stage2t exact child exception"
    )

    _install_engine_factory(
        monkeypatch,
        [error],
    )

    with pytest.raises(RuntimeError) as exc_info:
        _future_method(
            pipeline,
            "submit_scene_generation",
        )(object())

    assert exc_info.value is error


def test_movie_pipeline_submission_bridge_does_not_mutate_pipeline_state(
    monkeypatch,
):
    provider = object()
    pipeline = _pipeline_without_constructor(
        object(),
        provider,
    )
    pipeline.ai_director = object()
    pipeline.scene_builder = object()
    pipeline.generation_queue = object()
    pipeline.production_orchestrator = object()
    pipeline.reactive_orchestrator = object()
    pipeline._scene_inputs = {}

    before = {
        name: id(value)
        for name, value in pipeline.__dict__.items()
    }

    _install_engine_factory(
        monkeypatch,
        [object()],
    )

    _future_method(
        pipeline,
        "submit_scene_generation",
    )(object())

    after = {
        name: id(value)
        for name, value in pipeline.__dict__.items()
    }

    assert after == before


def test_legacy_movie_pipeline_paths_do_not_auto_submit_stage2t():
    for method_name in (
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
    ):
        source = textwrap.dedent(
            inspect.getsource(
                getattr(MoviePipeline, method_name)
            )
        )
        tree = ast.parse(source)

        called_attrs = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }

        assert "submit_scene_generation" not in called_attrs


def test_movie_pipeline_submission_bridge_is_bounded_delegation_only():
    method = getattr(
        MoviePipeline,
        "submit_scene_generation",
        None,
    )

    assert callable(method), (
        "Stage 2T RED: MoviePipeline.submit_scene_generation is missing"
    )

    tree = ast.parse(
        textwrap.dedent(
            inspect.getsource(method)
        )
    )

    nodes = list(ast.walk(tree))

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

    calls = [
        node.func.attr
        for node in nodes
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]

    assert calls.count("submit_scene_generation") == 1
    assert "inspect_scene_lifecycle" not in calls
    assert "advance_scene_once" not in calls
    assert "generate_scene" not in calls
    assert "process_all" not in calls
    assert "add_task" not in calls


@pytest.mark.parametrize(
    "case",
    [
        "none",
        "empty_name",
        "missing_generate",
        "missing_capabilities",
    ],
)
def test_explicit_engine_submission_rejects_incompatible_provider_before_output(
    tmp_path,
    case,
):
    _write_render_plan(tmp_path)

    provider_calls = []

    def recording_generate(*args, **kwargs):
        provider_calls.append(("generate", args, kwargs))
        return {
            "status": "generated",
            "provider": PROVIDER_NAME,
        }

    def recording_capabilities():
        provider_calls.append(("capabilities",))
        return {
            "media_types": ["video"],
            "resolutions": ["3840x2160"],
            "fps": [60],
            "hdr": [True],
            "color_depth": [10],
        }

    if case == "none":
        provider = None
    elif case == "empty_name":
        provider = SimpleNamespace(
            name="",
            generate=recording_generate,
            capabilities=recording_capabilities,
        )
    elif case == "missing_generate":
        provider = SimpleNamespace(
            name=PROVIDER_NAME,
            generate=None,
            capabilities=recording_capabilities,
        )
    else:
        provider = SimpleNamespace(
            name=PROVIDER_NAME,
            generate=recording_generate,
            capabilities=None,
        )

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    # This lookup is deliberately outside pytest.raises:
    # while Stage 2T entrypoint is absent, RED must fail here rather
    # than falsely pass because "missing method" is treated as the
    # expected provider-validation exception.
    method = _future_method(
        engine,
        "submit_scene_generation",
    )

    with pytest.raises(Exception):
        method(
            SCENE_ID,
            provider=provider,
        )

    assert provider_calls == []

    assert not (
        tmp_path
        / "render_output"
        / f"scene_{SCENE_ID:03d}"
        / "generation_result.json"
    ).exists()

    assert not (
        tmp_path
        / "generation_jobs"
        / "submitted"
    ).exists()


def test_explicit_engine_submission_never_routes_or_resolves_default_provider(
    tmp_path,
):
    _write_render_plan(tmp_path)

    exact_provider = RecordingProvider()

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    engine.provider_router = BombRouter()
    engine.provider_catalog = object()
    engine.provider_manager = BombManager()

    result = _explicit_submit(
        engine,
        SCENE_ID,
        exact_provider,
    )

    assert isinstance(result, str)
    assert len(exact_provider.calls) == 1

    assert len(engine.queue.tasks) == 1
    assert engine.queue.tasks[0].provider is exact_provider


def test_explicit_engine_submission_uses_same_exact_provider_for_every_shot(
    tmp_path,
):
    _write_render_plan(
        tmp_path,
        shot_count=3,
    )

    exact_provider = RecordingProvider()

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    engine.provider_router = BombRouter()
    engine.provider_manager = BombManager()

    _explicit_submit(
        engine,
        SCENE_ID,
        exact_provider,
    )

    assert len(engine.queue.tasks) == 3
    assert all(
        task.provider is exact_provider
        for task in engine.queue.tasks
    )

    assert len(exact_provider.calls) == 3


def test_explicit_async_submission_persists_exact_provider_identity_and_job_id(
    tmp_path,
):
    _write_render_plan(tmp_path)

    job_id = "stage2t-job-001"

    def async_result(provider, _prompt, _kwargs):
        return {
            "status": "submitted",
            "job_id": job_id,
            "provider": provider.name,
        }

    exact_provider = RecordingProvider(
        result_factory=async_result,
    )

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    engine.provider_router = BombRouter()
    engine.provider_manager = BombManager()

    output_path = _explicit_submit(
        engine,
        SCENE_ID,
        exact_provider,
    )

    output = json.loads(
        open(output_path, "r", encoding="utf-8").read()
    )

    assert output["submitted"] == 1
    assert output["tasks"][0]["provider"] == PROVIDER_NAME
    assert output["tasks"][0]["result"]["provider"] == PROVIDER_NAME
    assert output["tasks"][0]["result"]["job_id"] == job_id

    receipts = list(
        (
            tmp_path
            / "generation_jobs"
            / "submitted"
        ).glob("*.json")
    )

    assert len(receipts) == 1

    receipt = json.loads(
        receipts[0].read_text(
            encoding="utf-8"
        )
    )

    assert receipt["provider"] == PROVIDER_NAME
    assert receipt["job_id"] == job_id


def test_explicit_synchronous_submission_preserves_synchronous_completion(
    tmp_path,
):
    _write_render_plan(tmp_path)

    exact_provider = RecordingProvider()

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    engine.provider_router = BombRouter()
    engine.provider_manager = BombManager()

    output_path = _explicit_submit(
        engine,
        SCENE_ID,
        exact_provider,
    )

    output = json.loads(
        open(output_path, "r", encoding="utf-8").read()
    )

    assert output["generated"] == 1
    assert output["submitted"] == 0
    assert output["failed"] == 0
    assert output["tasks"][0]["status"] == "done"
    assert (
        output["tasks"][0]["result"]["marker"]
        == "stage2t-sync-result"
    )


def test_explicit_submission_preserves_model_policy_and_selected_model_on_tasks(
    tmp_path,
):
    _write_render_plan(tmp_path)

    exact_provider = RecordingProvider()

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    model_policy_sentinel = object()
    engine.model_policy = model_policy_sentinel

    engine.provider_router = BombRouter()
    engine.provider_manager = BombManager()

    _explicit_submit(
        engine,
        SCENE_ID,
        exact_provider,
    )

    assert len(engine.queue.tasks) == 1

    task = engine.queue.tasks[0]

    assert task.model_policy is model_policy_sentinel
    assert (
        task.metadata["shot_model_selection"]
        ["selected_model"]["name"]
        == "stage2t-model"
    )


def test_explicit_submission_does_not_auto_inspect_or_advance_lifecycle(
    tmp_path,
):
    _write_render_plan(tmp_path)

    exact_provider = RecordingProvider()

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    engine.provider_router = BombRouter()
    engine.provider_manager = BombManager()

    def forbidden(*_args, **_kwargs):
        raise AssertionError(
            "Stage 2T explicit submission must STOP after submission path"
        )

    engine.inspect_scene_lifecycle = forbidden
    engine.advance_scene_once = forbidden

    _explicit_submit(
        engine,
        SCENE_ID,
        exact_provider,
    )


def test_existing_generate_scene_still_uses_router_and_provider_manager(
    tmp_path,
):
    _write_render_plan(tmp_path)

    routed_provider = RecordingProvider(
        name="stage2t-router-provider"
    )

    class RouterSpy:
        def __init__(self):
            self.calls = []

        def select(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return routed_provider

    class ManagerSpy:
        def __init__(self):
            self.calls = []

        def get(self, name):
            self.calls.append(name)
            if name == routed_provider.name:
                return routed_provider
            return None

    engine = GenerationEngine(
        project_path=tmp_path,
    )

    router = RouterSpy()
    manager = ManagerSpy()

    engine.provider_router = router
    engine.provider_manager = manager

    output_path = engine.generate_scene(
        SCENE_ID
    )

    assert isinstance(output_path, str)
    assert router.calls == [
        (("video",), {"mode": "free"})
    ]
    assert manager.calls == [
        routed_provider.name
    ]
    assert len(routed_provider.calls) == 1


def test_stage2t_does_not_require_changes_to_queue_provider_or_lifecycle_classes():
    source = inspect.getsource(
        generation_engine_module
    )

    assert "submit_scene_generation" in source, (
        "Stage 2T RED: GenerationEngine explicit submission entrypoint "
        "is not implemented yet"
    )

    forbidden_direct_dependencies = {
        "GenerationLifecycleCoordinator",
        "GenerationJobLifecycle",
        "GenerationJobResultLifecycle",
        "GenerationJobAssetLifecycle",
        "GenerationResultReconciler",
        "GenerationTerminalReconciler",
    }

    tree = ast.parse(source)

    used_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

    assert used_names.isdisjoint(
        forbidden_direct_dependencies
    )
