import ast
import inspect
import textwrap

import pytest

import core.movie_engine.movie_pipeline as movie_pipeline_module
from core.movie_engine.movie_pipeline import MoviePipeline


METHOD = "prepare_scene_generation"


class SceneIdentitySentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2U bridge must not {operation} scene_id"
        )

    def __int__(self):
        self._reject("convert")

    def __index__(self):
        self._reject("index")

    def __str__(self):
        self._reject("stringify")

    def __format__(self, _spec):
        self._reject("format")

    def __copy__(self):
        self._reject("copy")

    def __deepcopy__(self, _memo):
        self._reject("deep-copy")


class Stage2UError(RuntimeError):
    pass


class StoryboardInstanceSpy:
    def __init__(self, effect, events):
        self.effect = effect
        self.events = events
        self.calls = []

    def create_storyboard_from_director(self, scene_id):
        self.calls.append(scene_id)
        self.events.append(
            ("storyboard_create", scene_id)
        )

        if isinstance(self.effect, BaseException):
            raise self.effect

        return self.effect


class StoryboardFactorySpy:
    def __init__(self, effects, events):
        self.effects = list(effects)
        self.events = events
        self.calls = []
        self.instances = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        self.events.append(
            ("storyboard_ctor", args, kwargs)
        )

        instance = StoryboardInstanceSpy(
            self.effects[len(self.instances)],
            self.events,
        )
        self.instances.append(instance)
        return instance


class RendererInstanceSpy:
    def __init__(self, effect, events):
        self.effect = effect
        self.events = events
        self.calls = []

    def create_render_plan(self, scene_id):
        self.calls.append(scene_id)
        self.events.append(
            ("render_plan_create", scene_id)
        )

        if isinstance(self.effect, BaseException):
            raise self.effect

        return self.effect


class RendererFactorySpy:
    def __init__(self, effects, events):
        self.effects = list(effects)
        self.events = events
        self.calls = []
        self.instances = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        self.events.append(
            ("renderer_ctor", args, kwargs)
        )

        instance = RendererInstanceSpy(
            self.effects[len(self.instances)],
            self.events,
        )
        self.instances.append(instance)
        return instance


def _future_method(target):
    method = getattr(target, METHOD, None)
    assert callable(method), (
        "Stage 2U RED: "
        "MoviePipeline.prepare_scene_generation is missing"
    )
    return method


def _pipeline_without_constructor(project_path):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.project_path = project_path
    return pipeline


def _install_factories(
    monkeypatch,
    storyboard_effects,
    renderer_effects,
):
    events = []

    storyboard_factory = StoryboardFactorySpy(
        storyboard_effects,
        events,
    )
    renderer_factory = RendererFactorySpy(
        renderer_effects,
        events,
    )

    monkeypatch.setattr(
        movie_pipeline_module,
        "StoryboardEngine",
        storyboard_factory,
        raising=False,
    )

    monkeypatch.setattr(
        movie_pipeline_module,
        "ShotRenderer",
        renderer_factory,
        raising=False,
    )

    return (
        events,
        storyboard_factory,
        renderer_factory,
    )


def _assert_exact_project_path_call(call, project_path):
    args, kwargs = call

    if args:
        assert len(args) == 1
        assert args[0] is project_path
        assert kwargs == {}
        return

    assert set(kwargs) == {"project_path"}
    assert kwargs["project_path"] is project_path


def _called_attribute_names(method):
    source = textwrap.dedent(
        inspect.getsource(method)
    )
    tree = ast.parse(source)

    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    }


def _parent_map(tree):
    parents = {}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    return parents


def test_stage2u_public_bridge_exists():
    assert callable(
        getattr(
            MoviePipeline,
            METHOD,
            None,
        )
    ), (
        "Stage 2U RED: "
        "MoviePipeline.prepare_scene_generation is missing"
    )


def test_stage2u_exact_order_project_path_scene_id_and_return(
    monkeypatch,
):
    project_path = object()
    scene_id = SceneIdentitySentinel()

    storyboard_result = object()
    render_plan_result = object()

    pipeline = _pipeline_without_constructor(
        project_path
    )

    (
        events,
        storyboard_factory,
        renderer_factory,
    ) = _install_factories(
        monkeypatch,
        [storyboard_result],
        [render_plan_result],
    )

    actual = _future_method(
        pipeline
    )(scene_id)

    assert actual is render_plan_result

    assert len(storyboard_factory.calls) == 1
    assert len(renderer_factory.calls) == 1

    _assert_exact_project_path_call(
        storyboard_factory.calls[0],
        project_path,
    )

    _assert_exact_project_path_call(
        renderer_factory.calls[0],
        project_path,
    )

    assert [
        event[0]
        for event in events
    ] == [
        "storyboard_ctor",
        "storyboard_create",
        "renderer_ctor",
        "render_plan_create",
    ]

    assert (
        storyboard_factory.instances[0].calls
        == [scene_id]
    )

    assert (
        renderer_factory.instances[0].calls
        == [scene_id]
    )

    assert (
        storyboard_factory.instances[0].calls[0]
        is scene_id
    )

    assert (
        renderer_factory.instances[0].calls[0]
        is scene_id
    )


def test_stage2u_uses_fresh_components_on_every_call(
    monkeypatch,
):
    project_path = object()

    pipeline = _pipeline_without_constructor(
        project_path
    )

    first_result = object()
    second_result = object()

    (
        _events,
        storyboard_factory,
        renderer_factory,
    ) = _install_factories(
        monkeypatch,
        [object(), object()],
        [first_result, second_result],
    )

    method = _future_method(pipeline)

    assert method(object()) is first_result
    assert method(object()) is second_result

    assert len(storyboard_factory.instances) == 2
    assert len(renderer_factory.instances) == 2

    assert (
        storyboard_factory.instances[0]
        is not storyboard_factory.instances[1]
    )

    assert (
        renderer_factory.instances[0]
        is not renderer_factory.instances[1]
    )

    for call in storyboard_factory.calls:
        _assert_exact_project_path_call(
            call,
            project_path,
        )

    for call in renderer_factory.calls:
        _assert_exact_project_path_call(
            call,
            project_path,
        )


def test_stage2u_storyboard_failure_prevents_renderer_construction(
    monkeypatch,
):
    pipeline = _pipeline_without_constructor(
        object()
    )

    error = Stage2UError(
        "stage2u storyboard failure"
    )

    (
        events,
        storyboard_factory,
        renderer_factory,
    ) = _install_factories(
        monkeypatch,
        [error],
        [object()],
    )

    method = _future_method(pipeline)

    with pytest.raises(Stage2UError) as exc_info:
        method(object())

    assert exc_info.value is error

    assert len(storyboard_factory.instances) == 1

    assert renderer_factory.calls == []
    assert renderer_factory.instances == []

    assert [
        event[0]
        for event in events
    ] == [
        "storyboard_ctor",
        "storyboard_create",
    ]


def test_stage2u_render_plan_exception_propagates_exactly(
    monkeypatch,
):
    pipeline = _pipeline_without_constructor(
        object()
    )

    error = Stage2UError(
        "stage2u render-plan failure"
    )

    (
        events,
        _storyboard_factory,
        renderer_factory,
    ) = _install_factories(
        monkeypatch,
        [object()],
        [error],
    )

    method = _future_method(pipeline)

    with pytest.raises(Stage2UError) as exc_info:
        method(object())

    assert exc_info.value is error

    assert len(renderer_factory.instances) == 1

    assert [
        event[0]
        for event in events
    ] == [
        "storyboard_ctor",
        "storyboard_create",
        "renderer_ctor",
        "render_plan_create",
    ]


def test_stage2u_bridge_does_not_mutate_pipeline_state(
    monkeypatch,
):
    pipeline = _pipeline_without_constructor(
        object()
    )

    pipeline.ai_director = object()
    pipeline.scene_builder = object()
    pipeline.generation_queue = object()
    pipeline.video_provider = object()
    pipeline.production_orchestrator = object()
    pipeline.reactive_orchestrator = object()
    pipeline._scene_inputs = {}

    before = {
        name: id(value)
        for name, value
        in pipeline.__dict__.items()
    }

    _install_factories(
        monkeypatch,
        [object()],
        [object()],
    )

    _future_method(
        pipeline
    )(object())

    after = {
        name: id(value)
        for name, value
        in pipeline.__dict__.items()
    }

    assert after == before


def test_stage2u_bridge_is_bounded_and_discards_storyboard_result():
    method = _future_method(
        MoviePipeline
    )

    source = textwrap.dedent(
        inspect.getsource(method)
    )

    tree = ast.parse(source)
    nodes = list(ast.walk(tree))
    parents = _parent_map(tree)

    forbidden_control = (
        ast.For,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.If,
        ast.IfExp,
        ast.Match,
        ast.AsyncFunctionDef,
        ast.Await,
        ast.Yield,
        ast.YieldFrom,
        ast.Lambda,
    )

    assert not any(
        isinstance(node, forbidden_control)
        for node in nodes
    )

    storyboard_calls = [
        node
        for node in nodes
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr
        == "create_storyboard_from_director"
    ]

    render_calls = [
        node
        for node in nodes
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr
        == "create_render_plan"
    ]

    assert len(storyboard_calls) == 1
    assert len(render_calls) == 1

    # Binding Stage 2U rule:
    # storyboard return value is deliberately discarded.
    assert isinstance(
        parents[storyboard_calls[0]],
        ast.Expr,
    )

    # Exact child return:
    # render-plan result is returned directly.
    assert isinstance(
        parents[render_calls[0]],
        ast.Return,
    )

    assert (
        storyboard_calls[0].lineno
        < render_calls[0].lineno
    )

    attribute_calls = [
        node.func.attr
        for node in nodes
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    ]

    forbidden_calls = {
        "analyze_scene",
        "load_direction",
        "submit_scene_generation",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "generate_scene",
        "create_scene",
        "process_all",
        "add_task",
        "read_text",
        "write_text",
        "mkdir",
        "exists",
    }

    assert not (
        set(attribute_calls)
        & forbidden_calls
    )

    name_calls = {
        node.func.id
        for node in nodes
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }

    assert "StoryboardEngine" in name_calls
    assert "ShotRenderer" in name_calls

    forbidden_names = {
        "GenerationEngine",
        "GenerationQueue",
        "GenerationTask",
        "ModelRouter",
        "ShotModelSelector",
        "ProviderManager",
        "ProviderRouter",
        "ProviderCatalog",
        "Path",
        "open",
        "json",
    }

    assert not (
        name_calls
        & forbidden_names
    )

    for node in nodes:
        if isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
            ),
        ):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )

            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(
                        target.value,
                        ast.Name,
                    )
                    and target.value.id == "self"
                ):
                    raise AssertionError(
                        "Stage 2U bridge must not "
                        "cache or mutate pipeline state"
                    )


def test_stage2u_legacy_paths_do_not_auto_prepare():
    for method_name in (
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
    ):
        method = getattr(
            MoviePipeline,
            method_name,
        )

        assert (
            METHOD
            not in _called_attribute_names(method)
        )


def test_stage2u_stage2s_and_stage2t_paths_do_not_auto_prepare():
    for method_name in (
        "_new_generation_lifecycle_engine",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "submit_scene_generation",
    ):
        method = getattr(
            MoviePipeline,
            method_name,
        )

        assert (
            METHOD
            not in _called_attribute_names(method)
        )


def test_stage2u_components_are_not_cached_in_movie_pipeline_constructor():
    source = textwrap.dedent(
        inspect.getsource(
            MoviePipeline.__init__
        )
    )

    tree = ast.parse(source)

    stored_self_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }

    assert "storyboard_engine" not in stored_self_attributes
    assert "shot_renderer" not in stored_self_attributes
    assert "generation_preparer" not in stored_self_attributes
