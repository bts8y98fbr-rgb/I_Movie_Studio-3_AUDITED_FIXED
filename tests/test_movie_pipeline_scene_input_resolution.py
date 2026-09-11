import ast
import inspect
import textwrap

import pytest

from core.movie_engine.movie_pipeline import MoviePipeline


METHOD = "_resolve_scene_input"


class SceneIdSentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2Y resolution must not {operation} scene_id"
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
            f"Stage 2Y resolution must not {operation} duration"
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
            "scene data resolution snapshot failed"
        )


class ForbiddenStateBomb:
    def __getattribute__(self, name):
        raise AssertionError(
            "Stage 2Y resolution must not access "
            f"unrelated pipeline state: {name}"
        )


def _future_method(target):
    return getattr(
        target,
        METHOD,
    )


def _bomb(name):
    def forbidden(*_args, **_kwargs):
        raise AssertionError(
            f"Stage 2Y resolution must not call {name}"
        )

    return forbidden


def _pipeline():
    pipeline = MoviePipeline.__new__(
        MoviePipeline
    )
    pipeline._scene_inputs = {}

    pipeline.reactive_orchestrator = (
        ForbiddenStateBomb()
    )
    pipeline.ai_director = ForbiddenStateBomb()
    pipeline.generation_queue = ForbiddenStateBomb()
    pipeline.scene_builder = ForbiddenStateBomb()
    pipeline.video_provider = ForbiddenStateBomb()
    pipeline.production_orchestrator = (
        ForbiddenStateBomb()
    )

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
        "_register_scene_input",
    ):
        setattr(
            pipeline,
            name,
            _bomb(name),
        )

    return pipeline


def _method_ast():
    method = _future_method(
        MoviePipeline
    )

    source = textwrap.dedent(
        inspect.getsource(method)
    )

    tree = ast.parse(source)
    node = tree.body[0]

    assert isinstance(
        node,
        ast.FunctionDef,
    )

    return node


def _called_attributes(node):
    return {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(
            child.func,
            ast.Attribute,
        )
    }


def _used_names(node):
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
    }


def test_stage2y_internal_resolution_boundary_exists():
    method = _future_method(
        MoviePipeline
    )

    assert callable(method)


def test_stage2y_signature_is_exact():
    method = _future_method(
        MoviePipeline
    )

    signature = inspect.signature(
        method
    )

    assert list(
        signature.parameters
    ) == [
        "self",
        "scene_id",
    ]

    assert all(
        parameter.default
        is inspect.Parameter.empty
        for parameter
        in signature.parameters.values()
    )


def test_stage2y_missing_exact_key_returns_none_without_mutation():
    pipeline = _pipeline()

    existing_id = object()
    duration = object()

    registered = {
        "scene_data": {
            "stable": True,
        },
        "duration": duration,
    }

    pipeline._scene_inputs[
        existing_id
    ] = registered

    missing_id = SceneIdSentinel()

    before_keys = list(
        pipeline._scene_inputs
    )

    result = _future_method(
        pipeline
    )(
        missing_id
    )

    assert result is None

    assert list(
        pipeline._scene_inputs
    ) == before_keys

    assert pipeline._scene_inputs[
        existing_id
    ] is registered


def test_stage2y_hit_returns_fresh_outer_mapping_and_shallow_scene_data_snapshot():
    pipeline = _pipeline()

    scene_id = SceneIdSentinel()
    duration = DurationSentinel()

    nested = {
        "camera": "wide",
    }

    stored_scene_data = {
        "title": "Scene A",
        "nested": nested,
    }

    registered = {
        "scene_data": stored_scene_data,
        "duration": duration,
    }

    pipeline._scene_inputs[
        scene_id
    ] = registered

    result = _future_method(
        pipeline
    )(
        scene_id
    )

    assert result == {
        "scene_data": stored_scene_data,
        "duration": duration,
    }

    assert result is not registered

    assert (
        result["scene_data"]
        is not stored_scene_data
    )

    assert (
        result["scene_data"]["nested"]
        is nested
    )

    assert result["duration"] is duration


def test_stage2y_exact_scene_id_and_duration_are_not_normalized():
    pipeline = _pipeline()

    scene_id = SceneIdSentinel()
    duration = DurationSentinel()

    pipeline._scene_inputs[
        scene_id
    ] = {
        "scene_data": {
            "prompt": "exact identity",
        },
        "duration": duration,
    }

    result = _future_method(
        pipeline
    )(
        scene_id
    )

    assert result["duration"] is duration

    assert result["scene_data"] == {
        "prompt": "exact identity",
    }


def test_stage2y_repeated_resolution_returns_fresh_snapshots():
    pipeline = _pipeline()

    scene_id = object()

    nested = {
        "lens": "50mm",
    }

    stored_scene_data = {
        "title": "Repeated",
        "nested": nested,
    }

    pipeline._scene_inputs[
        scene_id
    ] = {
        "scene_data": stored_scene_data,
        "duration": 8,
    }

    first = _future_method(
        pipeline
    )(
        scene_id
    )

    second = _future_method(
        pipeline
    )(
        scene_id
    )

    assert first is not second

    assert (
        first["scene_data"]
        is not second["scene_data"]
    )

    assert (
        first["scene_data"]
        is not stored_scene_data
    )

    assert (
        second["scene_data"]
        is not stored_scene_data
    )

    assert (
        first["scene_data"]["nested"]
        is nested
    )

    assert (
        second["scene_data"]["nested"]
        is nested
    )


def test_stage2y_resolved_top_level_mutation_does_not_change_registration():
    pipeline = _pipeline()

    scene_id = object()
    duration = object()

    stored_scene_data = {
        "title": "Original",
        "shot_count": 3,
    }

    registered = {
        "scene_data": stored_scene_data,
        "duration": duration,
    }

    pipeline._scene_inputs[
        scene_id
    ] = registered

    result = _future_method(
        pipeline
    )(
        scene_id
    )

    result["scene_data"][
        "title"
    ] = "Changed"

    result["scene_data"][
        "added"
    ] = True

    result["duration"] = object()
    result["extra"] = True

    assert registered == {
        "scene_data": {
            "title": "Original",
            "shot_count": 3,
        },
        "duration": duration,
    }

    assert (
        pipeline._scene_inputs[
            scene_id
        ]
        is registered
    )


def test_stage2y_resolution_does_not_mutate_registered_storage():
    pipeline = _pipeline()

    scene_id = object()
    duration = object()

    nested = []

    stored_scene_data = {
        "nested": nested,
        "value": 7,
    }

    registered = {
        "scene_data": stored_scene_data,
        "duration": duration,
    }

    pipeline._scene_inputs[
        scene_id
    ] = registered

    before_keys = list(
        pipeline._scene_inputs
    )

    result = _future_method(
        pipeline
    )(
        scene_id
    )

    assert list(
        pipeline._scene_inputs
    ) == before_keys

    assert (
        pipeline._scene_inputs[
            scene_id
        ]
        is registered
    )

    assert (
        registered["scene_data"]
        is stored_scene_data
    )

    assert (
        registered["scene_data"]["nested"]
        is nested
    )

    assert result["duration"] is duration


def test_stage2y_snapshot_failure_propagates_without_mutating_registration():
    pipeline = _pipeline()

    scene_id = object()
    failing_scene_data = FailingSceneData()
    duration = object()

    registered = {
        "scene_data": failing_scene_data,
        "duration": duration,
    }

    pipeline._scene_inputs[
        scene_id
    ] = registered

    with pytest.raises(
        SnapshotError
    ) as exc_info:
        _future_method(
            pipeline
        )(
            scene_id
        )

    assert str(
        exc_info.value
    ) == (
        "scene data resolution snapshot failed"
    )

    assert (
        pipeline._scene_inputs[
            scene_id
        ]
        is registered
    )

    assert (
        registered["scene_data"]
        is failing_scene_data
    )

    assert (
        registered["duration"]
        is duration
    )


def test_stage2y_resolution_has_no_generation_or_reactive_continuation():
    pipeline = _pipeline()

    scene_id = object()

    pipeline._scene_inputs[
        scene_id
    ] = {
        "scene_data": {
            "prompt": "resolve only",
        },
        "duration": object(),
    }

    result = _future_method(
        pipeline
    )(
        scene_id
    )

    assert set(result) == {
        "scene_data",
        "duration",
    }


def test_stage2y_ast_uses_exact_scene_id_without_normalization():
    node = _method_ast()

    used_names = _used_names(
        node
    )

    assert "scene_id" in used_names

    forbidden_normalizers = {
        "int",
        "str",
        "float",
        "bytes",
        "repr",
        "format",
    }

    assert not (
        used_names
        & forbidden_normalizers
    )


def test_stage2y_ast_has_no_retry_polling_scheduler_or_background_work():
    node = _method_ast()

    forbidden_nodes = (
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Match,
        ast.Lambda,
        ast.Await,
        ast.Yield,
        ast.YieldFrom,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )

    assert not any(
        isinstance(
            child,
            forbidden_nodes,
        )
        for child in ast.walk(node)
    )


def test_stage2y_ast_does_not_touch_generation_provider_reactive_or_persistence():
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
        "_register_scene_input",
        "analyze_scene",
        "load_direction",
        "generate_scene",
        "process_all",
        "add_task",
        "apply",
        "select",
        "read_text",
        "write_text",
        "exists",
        "sleep",
        "start",
        "submit",
        "schedule",
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
        "threading",
        "asyncio",
        "time",
    }

    assert not (
        _used_names(node)
        & forbidden_names
    )


def test_stage2y_ast_does_not_mutate_pipeline_state():
    node = _method_ast()

    mutation_targets = []

    for child in ast.walk(node):
        if isinstance(
            child,
            ast.Assign,
        ):
            mutation_targets.extend(
                child.targets
            )

        elif isinstance(
            child,
            (
                ast.AnnAssign,
                ast.AugAssign,
                ast.NamedExpr,
            ),
        ):
            mutation_targets.append(
                child.target
            )

        elif isinstance(
            child,
            ast.Delete,
        ):
            mutation_targets.extend(
                child.targets
            )

    for target in mutation_targets:
        self_attributes = {
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
                and item.value.id
                == "self"
            )
        }

        assert not self_attributes
