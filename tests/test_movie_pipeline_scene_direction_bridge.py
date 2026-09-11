import ast
from pathlib import Path

import pytest

import core.movie_engine.movie_pipeline as movie_pipeline_module
from core.movie_engine.movie_pipeline import MoviePipeline


SOURCE_PATH = Path(movie_pipeline_module.__file__)
FUTURE_METHODS = (
    "create_scene_direction",
    "load_scene_direction",
)
EXISTING_METHODS = (
    "create_scene",
    "regenerate_from_master_prompt",
    "_regenerate_scene_from_master_prompt",
    "prepare_scene_generation",
    "submit_scene_generation",
    "inspect_scene_lifecycle",
    "advance_scene_once",
)


class SceneIdSentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2V bridge must not {operation} scene_id"
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


class ProgrammingSentinel(RuntimeError):
    pass


class DirectorSpy:
    def __init__(self, analyze_result=None, load_result=None):
        self.analyze_result = analyze_result
        self.load_result = load_result
        self.analyze_calls = []
        self.load_calls = []
        self.analyze_error = None
        self.load_error = None

    def analyze_scene(self, *args):
        self.analyze_calls.append(args)
        if self.analyze_error is not None:
            raise self.analyze_error
        return self.analyze_result

    def load_direction(self, *args):
        self.load_calls.append(args)
        if self.load_error is not None:
            raise self.load_error
        return self.load_result


class DirectorConstructionBomb:
    def __init__(self, *_args, **_kwargs):
        raise AssertionError("Stage 2V must reuse pipeline.ai_director")


def _future_method(pipeline, name):
    method = getattr(pipeline, name, None)
    assert callable(method), (
        f"Stage 2V RED: MoviePipeline.{name} is missing"
    )
    return method


def _make_pipeline(director, project_path=None):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.project_path = project_path if project_path is not None else object()
    pipeline.ai_director = director
    pipeline.scene_builder = object()
    pipeline.generation_queue = object()
    pipeline.video_provider = object()
    pipeline.production_orchestrator = object()
    pipeline._scene_inputs = {"untouched": object()}
    pipeline.reactive_orchestrator = object()
    pipeline.model_policy = object()
    pipeline.provider_manager = object()
    pipeline.provider_catalog = object()
    pipeline.provider_router = object()
    pipeline.credentials = object()
    pipeline.quality_policy = object()
    pipeline.queue = object()
    return pipeline


def _snapshot_state(pipeline):
    return {
        "keys": tuple(pipeline.__dict__),
        "identities": {
            key: id(value)
            for key, value in pipeline.__dict__.items()
        },
    }


def _tree():
    return ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))


def _method_node(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    return None


def _call_attribute_names(node):
    return {
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
    }


def test_future_create_scene_direction_is_public_and_callable():
    assert callable(getattr(MoviePipeline, "create_scene_direction", None)), (
        "Stage 2V RED: MoviePipeline.create_scene_direction is missing"
    )


def test_future_load_scene_direction_is_public_and_callable():
    assert callable(getattr(MoviePipeline, "load_scene_direction", None)), (
        "Stage 2V RED: MoviePipeline.load_scene_direction is missing"
    )


def test_existing_module_level_aidirector_symbol_remains_available():
    assert movie_pipeline_module.AIDirector is not None


def test_create_scene_direction_preserves_director_and_argument_identity(
    monkeypatch,
):
    director = DirectorSpy()
    pipeline = _make_pipeline(director, project_path=object())
    monkeypatch.setattr(
        movie_pipeline_module,
        "AIDirector",
        DirectorConstructionBomb,
    )
    scene_id = SceneIdSentinel()
    scene_data = object()
    duration = object()
    result = object()
    director.analyze_result = result

    actual = _future_method(pipeline, "create_scene_direction")(
        scene_id,
        scene_data,
        duration,
    )

    assert actual is result
    assert director.analyze_calls == [(scene_id, scene_data, duration)]
    assert director.load_calls == []


def test_load_scene_direction_preserves_director_and_scene_id_identity(
    monkeypatch,
):
    director = DirectorSpy(load_result=object())
    pipeline = _make_pipeline(director)
    monkeypatch.setattr(
        movie_pipeline_module,
        "AIDirector",
        DirectorConstructionBomb,
    )
    scene_id = SceneIdSentinel()

    actual = _future_method(pipeline, "load_scene_direction")(scene_id)

    assert actual is director.load_result
    assert director.load_calls == [(scene_id,)]
    assert director.analyze_calls == []


@pytest.mark.parametrize(
    ("method_name", "director_method", "args"),
    [
        ("create_scene_direction", "analyze_scene", (object(), object(), object())),
        ("load_scene_direction", "load_direction", (object(),)),
    ],
)
@pytest.mark.parametrize(
    "error",
    [ValueError("stage2v-value"), TypeError("stage2v-type"), ProgrammingSentinel("stage2v-runtime")],
)
def test_stage2v_child_exception_identity_is_preserved(
    method_name,
    director_method,
    args,
    error,
):
    director = DirectorSpy()
    error_attr = {
        "analyze_scene": "analyze_error",
        "load_direction": "load_error",
    }[director_method]
    setattr(director, error_attr, error)
    pipeline = _make_pipeline(director)
    method = _future_method(pipeline, method_name)

    with pytest.raises(type(error)) as raised:
        method(*args)

    assert raised.value is error


def test_stage2v_bridges_leave_pipeline_state_unchanged(monkeypatch):
    director = DirectorSpy(analyze_result=object(), load_result=object())
    pipeline = _make_pipeline(director)
    before = _snapshot_state(pipeline)
    monkeypatch.setattr(
        movie_pipeline_module,
        "AIDirector",
        DirectorConstructionBomb,
    )

    _future_method(pipeline, "create_scene_direction")(
        SceneIdSentinel(),
        object(),
        object(),
    )
    _future_method(pipeline, "load_scene_direction")(SceneIdSentinel())

    assert _snapshot_state(pipeline) == before


def test_stage2v_methods_are_fresh_and_do_not_cache_results():
    director = DirectorSpy()
    first = object()
    second = object()
    director.analyze_result = first
    pipeline = _make_pipeline(director)
    create = _future_method(pipeline, "create_scene_direction")

    assert create(object(), object(), object()) is first
    director.analyze_result = second
    assert create(object(), object(), object()) is second
    assert len(director.analyze_calls) == 2


def test_stage2v_future_methods_are_minimal_direct_delegations():
    tree = _tree()
    for name in FUTURE_METHODS:
        node = _method_node(tree, name)
        assert node is not None, f"Stage 2V RED: method {name} is missing"
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ) and isinstance(body[0].value.value, str):
            body = body[1:]
        assert len(body) == 1
        assert isinstance(body[0], ast.Return)
        assert isinstance(body[0].value, ast.Call)
        assert isinstance(body[0].value.func, ast.Attribute)

        target = body[0].value.func.value

        assert isinstance(target, ast.Attribute)
        assert target.attr == "ai_director"
        assert isinstance(target.value, ast.Name)
        assert target.value.id == "self"

        expected_child = {
            "create_scene_direction": "analyze_scene",
            "load_scene_direction": "load_direction",
        }[name]

        assert body[0].value.func.attr == expected_child
        assert not any(
            isinstance(child, (ast.For, ast.While, ast.Try, ast.If, ast.Match, ast.AsyncFunctionDef))
            for child in ast.walk(node)
        )


def test_stage2v_methods_do_not_reference_scene_inputs_or_forbidden_orchestration():
    tree = _tree()
    forbidden = {
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
        "prepare_scene_generation",
        "submit_scene_generation",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "plan_scene",
        "process_all",
    }
    for name in FUTURE_METHODS:
        node = _method_node(tree, name)
        assert node is not None, f"Stage 2V RED: method {name} is missing"
        names = {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name)
        }

        attribute_names = {
            child.attr
            for child in ast.walk(node)
            if isinstance(child, ast.Attribute)
        }

        called_attrs = _call_attribute_names(node)

        assert "_scene_inputs" not in names
        assert "_scene_inputs" not in attribute_names
        assert not called_attrs.intersection(forbidden)


def test_existing_pipeline_methods_do_not_auto_invoke_stage2v_bridges():
    tree = _tree()
    for name in EXISTING_METHODS:
        node = _method_node(tree, name)
        assert node is not None
        called = _call_attribute_names(node)
        assert not called.intersection(set(FUTURE_METHODS))


def test_stage2v_does_not_add_a_second_lifecycle_or_provider_path():
    tree = _tree()
    for forbidden in (
        "plan_scene",
        "process_all",
        "prepare_scene_generation",
        "submit_scene_generation",
        "inspect_scene_lifecycle",
        "advance_scene_once",
    ):
        for name in FUTURE_METHODS:
            node = _method_node(tree, name)
            assert node is not None, f"Stage 2V RED: method {name} is missing"
            assert forbidden not in _call_attribute_names(node)
