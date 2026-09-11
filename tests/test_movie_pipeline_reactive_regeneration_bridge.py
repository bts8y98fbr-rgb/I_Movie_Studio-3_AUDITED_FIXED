import ast
import inspect
from pathlib import Path

import pytest

from core.movie_engine.movie_pipeline import MoviePipeline


SOURCE_PATH = Path("core/movie_engine/movie_pipeline.py")
METHOD_NAME = "_regenerate_scene_from_master_prompt"


class SceneIdSentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2Z-B must not {operation} scene_id"
        )

    def __int__(self):
        self._reject("convert")

    def __index__(self):
        self._reject("index")

    def __str__(self):
        self._reject("stringify")

    def __format__(self, _spec):
        self._reject("format")


class SnapshotError(RuntimeError):
    pass


class Stage2WError(RuntimeError):
    pass


class LegacyCreateSceneError(AssertionError):
    pass


def _method(pipeline):
    return getattr(pipeline, METHOD_NAME)


def _pipeline(*, resolved=None, w_result=None, resolver_error=None, w_error=None):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline._scene_inputs = {}
    resolver_calls = []
    w_calls = []
    create_scene_calls = []

    def resolve(scene_id):
        resolver_calls.append(scene_id)
        if resolver_error is not None:
            raise resolver_error
        return resolved

    def create_prepare_submit(scene_id, scene_data, duration):
        w_calls.append((scene_id, scene_data, duration))
        if w_error is not None:
            raise w_error
        return w_result

    def create_scene(*args, **kwargs):
        create_scene_calls.append((args, kwargs))
        raise LegacyCreateSceneError(
            "legacy create_scene must not be called"
        )

    pipeline._resolve_scene_input = resolve
    pipeline.create_prepare_submit_scene_generation = (
        create_prepare_submit
    )
    pipeline.create_scene = create_scene
    pipeline._register_scene_input = lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(
            AssertionError(
                "_register_scene_input must not be called"
            )
        )
    )
    pipeline._stage2za_probe = {
        "resolver_calls": resolver_calls,
        "w_calls": w_calls,
        "create_scene_calls": create_scene_calls,
    }
    return pipeline


def _method_ast():
    source = inspect.getsource(MoviePipeline.__dict__[METHOD_NAME])
    tree = ast.parse(inspect.cleandoc(source))
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_stage2zb_exact_numeric_string_id_reaches_resolver_and_stage2w():
    nested = {"camera": "wide"}
    resolved = {
        "scene_data": {
            "title": "Registered",
            "nested": nested,
        },
        "duration": object(),
    }
    stage2w_result = {"status": "submitted"}
    pipeline = _pipeline(resolved=resolved, w_result=stage2w_result)

    prompt = object()
    result = _method(pipeline)("01", prompt)

    assert result is stage2w_result
    assert pipeline._stage2za_probe["resolver_calls"] == ["01"]
    assert len(pipeline._stage2za_probe["w_calls"]) == 1
    scene_id, scene_data, duration = pipeline._stage2za_probe[
        "w_calls"
    ][0]
    assert scene_id == "01"
    assert scene_data["master_prompt"] is prompt
    assert scene_data["title"] == "Registered"
    assert scene_data["nested"] is nested
    assert duration is resolved["duration"]
    assert scene_data is not resolved["scene_data"]
    assert "master_prompt" not in resolved["scene_data"]


def test_stage2zb_opaque_scene_id_is_passed_by_identity():
    scene_id = SceneIdSentinel()
    resolved = {
        "scene_data": {"title": "Opaque"},
        "duration": object(),
    }
    pipeline = _pipeline(resolved=resolved, w_result=object())

    _method(pipeline)(scene_id, object())

    assert pipeline._stage2za_probe["resolver_calls"][0] is scene_id
    assert pipeline._stage2za_probe["w_calls"][0][0] is scene_id


def test_stage2zb_mixed_integer_registration_does_not_resolve_string_id():
    pipeline = _pipeline(resolved=None)
    pipeline._scene_inputs[1] = {
        "scene_data": {"title": "Integer registration"},
        "duration": 5,
    }

    result = _method(pipeline)("1", "prompt")

    assert result == {
        "status": "skipped",
        "scene_id": "1",
        "reason": "Scene is not registered in this pipeline",
    }
    assert pipeline._stage2za_probe["resolver_calls"] == ["1"]
    assert pipeline._stage2za_probe["w_calls"] == []


def test_stage2zb_missing_registration_returns_exact_skip_without_stage2w():
    pipeline = _pipeline(resolved=None)
    before = dict(pipeline._scene_inputs)

    result = _method(pipeline)("999", "prompt")

    assert result == {
        "status": "skipped",
        "scene_id": "999",
        "reason": "Scene is not registered in this pipeline",
    }
    assert pipeline._stage2za_probe["resolver_calls"] == ["999"]
    assert pipeline._stage2za_probe["w_calls"] == []
    assert pipeline._scene_inputs == before


@pytest.mark.parametrize(
    "stage2w_result",
    [
        {"status": "submitted", "generated_tasks": []},
        object(),
    ],
)
def test_stage2zb_stage2w_result_passes_through_by_identity(stage2w_result):
    resolved = {
        "scene_data": {"title": "Identity"},
        "duration": 7,
    }
    pipeline = _pipeline(resolved=resolved, w_result=stage2w_result)

    result = _method(pipeline)(1, "prompt")

    assert result is stage2w_result
    assert len(pipeline._stage2za_probe["w_calls"]) == 1
    assert pipeline._stage2za_probe["create_scene_calls"] == []


def test_stage2zb_transient_scene_data_copy_preserves_registration():
    nested = {"lens": "50mm"}
    original_scene_data = {
        "title": "Original",
        "nested": nested,
    }
    resolved = {
        "scene_data": original_scene_data,
        "duration": object(),
    }
    pipeline = _pipeline(resolved=resolved, w_result={"ok": True})

    _method(pipeline)(1, "replacement prompt")

    transient = pipeline._stage2za_probe["w_calls"][0][1]
    assert transient is not original_scene_data
    assert transient["nested"] is nested
    assert transient["master_prompt"] == "replacement prompt"
    assert original_scene_data == {
        "title": "Original",
        "nested": nested,
    }
    assert resolved["scene_data"] is original_scene_data


def test_stage2zb_resolver_exception_propagates_and_stage2w_does_not_run():
    error = SnapshotError("resolver failed")
    pipeline = _pipeline(resolver_error=error)

    with pytest.raises(SnapshotError) as exc_info:
        _method(pipeline)("01", "prompt")

    assert exc_info.value is error
    assert pipeline._stage2za_probe["w_calls"] == []


def test_stage2zb_stage2w_exception_propagates_without_wrapping():
    error = Stage2WError("stage2w failed")
    resolved = {
        "scene_data": {"title": "Failure"},
        "duration": 5,
    }
    pipeline = _pipeline(resolved=resolved, w_error=error)

    with pytest.raises(Stage2WError) as exc_info:
        _method(pipeline)(1, "prompt")

    assert exc_info.value is error
    assert len(pipeline._stage2za_probe["w_calls"]) == 1


def test_stage2zb_repeated_calls_do_not_mutate_canonical_resolution():
    nested = []
    resolved = {
        "scene_data": {"nested": nested, "title": "Stable"},
        "duration": object(),
    }
    pipeline = _pipeline(resolved=resolved, w_result={"ok": True})

    _method(pipeline)(1, "first")
    _method(pipeline)(1, "second")

    first = pipeline._stage2za_probe["w_calls"][0][1]
    second = pipeline._stage2za_probe["w_calls"][1][1]
    assert first is not second
    assert first["master_prompt"] == "first"
    assert second["master_prompt"] == "second"
    assert resolved == {
        "scene_data": {"nested": nested, "title": "Stable"},
        "duration": resolved["duration"],
    }


def test_stage2zb_callback_source_uses_only_approved_boundaries():
    node = _method_ast()
    called_attributes = {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
    }
    direct_calls = {
        child.func.id
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
    }
    all_attributes = {
        child.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Attribute)
    }

    assert "_resolve_scene_input" in called_attributes
    assert "create_prepare_submit_scene_generation" in called_attributes
    assert "int" not in direct_calls
    assert "_scene_inputs" not in all_attributes
    assert "create_scene" not in called_attributes
    assert "_register_scene_input" not in called_attributes
    assert not {
        "create_scene_direction",
        "load_scene_direction",
        "prepare_scene_generation",
        "submit_scene_generation",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "process_all",
        "generate",
        "get_status",
        "get_result",
    }.intersection(called_attributes)
