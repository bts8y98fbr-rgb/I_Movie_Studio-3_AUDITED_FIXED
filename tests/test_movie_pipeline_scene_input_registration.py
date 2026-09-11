import ast
import inspect
import textwrap

import pytest

from core.movie_engine.movie_pipeline import MoviePipeline


METHOD = "_register_scene_input"


class SceneIdSentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2X registration must not {operation} scene_id"
        )

    def __int__(self):
        self._reject("convert")

    def __index__(self):
        self._reject("index")

    def __str__(self):
        self._reject("stringify")

    def __format__(self, _spec):
        self._reject("format")


class DurationSentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2X registration must not {operation} duration"
        )

    def __int__(self):
        self._reject("convert")

    def __float__(self):
        self._reject("float-convert")

    def __index__(self):
        self._reject("index")

    def __str__(self):
        self._reject("stringify")

    def __format__(self, _spec):
        self._reject("format")


class SnapshotError(RuntimeError):
    pass


class FailingSceneData:
    def __iter__(self):
        raise SnapshotError(
            "scene data snapshot failed"
        )


class ReactiveAccessBomb:
    def __getattribute__(self, name):
        raise AssertionError(
            "Stage 2X registration must not access "
            f"ReactiveOrchestrator state: {name}"
        )


def _future_method(target):
    method = getattr(target, METHOD, None)

    assert callable(method), (
        "Stage 2X RED: "
        "MoviePipeline._register_scene_input is missing"
    )

    return method


def _bomb(name):
    def forbidden(*_args, **_kwargs):
        raise AssertionError(
            f"Stage 2X registration must not call {name}"
        )

    return forbidden


def _pipeline():
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline._scene_inputs = {}
    pipeline.reactive_orchestrator = ReactiveAccessBomb()

    for name in (
        "create_scene_direction",
        "load_scene_direction",
        "prepare_scene_generation",
        "submit_scene_generation",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "create_prepare_submit_scene_generation",
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
    ):
        setattr(
            pipeline,
            name,
            _bomb(name),
        )

    return pipeline


def _method_ast():
    method = _future_method(MoviePipeline)

    source = textwrap.dedent(
        inspect.getsource(method)
    )

    tree = ast.parse(source)
    node = tree.body[0]

    assert isinstance(node, ast.FunctionDef)

    return node


def _called_attributes(node):
    return {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
    }


def _used_names(node):
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
    }


def test_stage2x_internal_registration_boundary_exists():
    assert callable(
        getattr(
            MoviePipeline,
            METHOD,
            None,
        )
    ), (
        "Stage 2X RED: "
        "MoviePipeline._register_scene_input is missing"
    )


def test_stage2x_signature_is_exact():
    method = _future_method(MoviePipeline)
    signature = inspect.signature(method)

    assert list(
        signature.parameters
    ) == [
        "self",
        "scene_id",
        "scene_data",
        "duration",
    ]

    assert all(
        parameter.default
        is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )


def test_stage2x_registers_exact_key_duration_and_shallow_snapshot():
    pipeline = _pipeline()

    scene_id = SceneIdSentinel()
    duration = DurationSentinel()
    nested = {
        "camera": "wide",
    }

    scene_data = {
        "title": "Scene A",
        "nested": nested,
    }

    result = _future_method(pipeline)(
        scene_id,
        scene_data,
        duration,
    )

    assert result is None

    assert list(
        pipeline._scene_inputs
    ) == [
        scene_id,
    ]

    registered = pipeline._scene_inputs[
        scene_id
    ]

    assert set(registered) == {
        "scene_data",
        "duration",
    }

    snapshot = registered["scene_data"]

    assert snapshot == scene_data
    assert snapshot is not scene_data
    assert snapshot["nested"] is nested

    assert registered["duration"] is duration


def test_stage2x_external_top_level_mutation_does_not_change_snapshot():
    pipeline = _pipeline()

    scene_id = object()

    scene_data = {
        "title": "Original",
        "shot_count": 3,
    }

    _future_method(pipeline)(
        scene_id,
        scene_data,
        7,
    )

    scene_data["title"] = "Changed"
    scene_data["added_later"] = True

    snapshot = pipeline._scene_inputs[
        scene_id
    ]["scene_data"]

    assert snapshot == {
        "title": "Original",
        "shot_count": 3,
    }


def test_stage2x_registration_does_not_mutate_input_scene_data():
    pipeline = _pipeline()

    scene_data = {
        "title": "Untouched",
        "shots": ["a", "b"],
    }

    before = dict(scene_data)

    _future_method(pipeline)(
        object(),
        scene_data,
        object(),
    )

    assert scene_data == before
    assert scene_data["shots"] is before["shots"]


def test_stage2x_reregistration_replaces_snapshot_instead_of_merging():
    pipeline = _pipeline()

    scene_id = object()

    first_duration = object()
    second_duration = object()

    _future_method(pipeline)(
        scene_id,
        {
            "old": 1,
            "remove_me": 2,
        },
        first_duration,
    )

    _future_method(pipeline)(
        scene_id,
        {
            "new": 3,
        },
        second_duration,
    )

    registered = pipeline._scene_inputs[
        scene_id
    ]

    assert registered["scene_data"] == {
        "new": 3,
    }

    assert registered["duration"] is second_duration


def test_stage2x_snapshot_failure_propagates_and_preserves_other_registration():
    pipeline = _pipeline()

    existing_id = object()

    pipeline._scene_inputs[
        existing_id
    ] = {
        "scene_data": {
            "stable": True,
        },
        "duration": 9,
    }

    failing_id = object()

    with pytest.raises(
        SnapshotError
    ) as exc_info:
        _future_method(pipeline)(
            failing_id,
            FailingSceneData(),
            object(),
        )

    assert str(exc_info.value) == (
        "scene data snapshot failed"
    )

    assert pipeline._scene_inputs[
        existing_id
    ] == {
        "scene_data": {
            "stable": True,
        },
        "duration": 9,
    }

    assert failing_id not in pipeline._scene_inputs


def test_stage2x_registration_has_no_generation_or_reactive_continuation():
    pipeline = _pipeline()

    result = _future_method(pipeline)(
        object(),
        {
            "prompt": "registered only",
        },
        object(),
    )

    assert result is None
    assert len(pipeline._scene_inputs) == 1


def test_stage2x_does_not_mutate_pipeline_state_outside_scene_input_storage():
    pipeline = _pipeline()

    marker = object()
    pipeline.stage2x_marker = marker

    before_keys = set(
        pipeline.__dict__
    )

    _future_method(pipeline)(
        object(),
        {
            "scene": "data",
        },
        object(),
    )

    assert set(
        pipeline.__dict__
    ) == before_keys

    assert pipeline.stage2x_marker is marker


def test_stage2x_ast_has_no_hidden_control_flow_retry_or_background_work():
    node = _method_ast()

    forbidden_nodes = (
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.If,
        ast.IfExp,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Match,
        ast.Lambda,
        ast.Await,
        ast.Yield,
        ast.YieldFrom,
    )

    assert not any(
        isinstance(child, forbidden_nodes)
        for child in ast.walk(node)
    )


def test_stage2x_ast_does_not_touch_generation_provider_reactive_or_persistence():
    node = _method_ast()

    forbidden_calls = {
        "create_scene_direction",
        "load_scene_direction",
        "prepare_scene_generation",
        "submit_scene_generation",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "create_prepare_submit_scene_generation",
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
        "analyze_scene",
        "load_direction",
        "generate_scene",
        "process_all",
        "add_task",
        "apply",
        "select",
        "get",
        "read_text",
        "write_text",
        "exists",
        "sleep",
    }

    assert not (
        _called_attributes(node)
        & forbidden_calls
    )

    forbidden_names = {
        "AIDirector",
        "StoryboardEngine",
        "ShotRenderer",
        "GenerationEngine",
        "GenerationQueue",
        "SceneBuilder",
        "ReactiveOrchestrator",
        "ProviderManager",
        "ProviderRouter",
        "ProviderCatalog",
        "ProviderRegistry",
        "ModelPolicy",
        "Path",
        "open",
    }

    assert not (
        _used_names(node)
        & forbidden_names
    )


def test_stage2x_ast_only_mutates_scene_input_storage_on_self():
    node = _method_ast()

    for child in ast.walk(node):
        targets = []

        if isinstance(child, ast.Assign):
            targets = child.targets
        elif isinstance(
            child,
            (
                ast.AnnAssign,
                ast.AugAssign,
            ),
        ):
            targets = [
                child.target,
            ]

        for target in targets:
            self_attributes = [
                item.attr
                for item in ast.walk(target)
                if (
                    isinstance(
                        item,
                        ast.Attribute,
                    )
                    and isinstance(
                        item.value,
                        ast.Name,
                    )
                    and item.value.id == "self"
                )
            ]

            assert set(
                self_attributes
            ) <= {
                "_scene_inputs",
            }
