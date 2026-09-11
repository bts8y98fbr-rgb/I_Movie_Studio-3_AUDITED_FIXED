import ast
import inspect
import textwrap

import pytest

from core.movie_engine.movie_pipeline import MoviePipeline


METHOD = "create_scene_generation"


class SceneIdSentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 3A entrypoint must not {operation} scene_id"
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


class DurationSentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 3A entrypoint must not {operation} duration"
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


class RegistrationError(RuntimeError):
    pass


class Stage2WError(RuntimeError):
    pass


class BoundarySpy:
    def __init__(self, *, registration_error=None, stage2w_error=None, result=None):
        self.registration_error = registration_error
        self.stage2w_error = stage2w_error
        self.result = result
        self.events = []

    def register(self, scene_id, scene_data, duration):
        self.events.append(("register", scene_id, scene_data, duration))
        if self.registration_error is not None:
            raise self.registration_error

    def stage2w(self, scene_id, scene_data, duration):
        self.events.append(("stage2w", scene_id, scene_data, duration))
        if self.stage2w_error is not None:
            raise self.stage2w_error
        return self.result


def _future_method(target):
    method = getattr(target, METHOD, None)
    assert callable(method), (
        "Stage 3A RED: MoviePipeline.create_scene_generation is missing"
    )
    return method


def _pipeline_with_spy(spy):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline._scene_inputs = {}
    pipeline._register_scene_input = spy.register
    pipeline.create_prepare_submit_scene_generation = spy.stage2w
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


def _attribute_calls(node):
    return [
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
    ]


def _self_store_names(node):
    names = []
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            targets = child.targets
        elif isinstance(child, (ast.AnnAssign, ast.AugAssign)):
            targets = [child.target]
        else:
            continue
        for target in targets:
            for item in ast.walk(target):
                if (
                    isinstance(item, ast.Attribute)
                    and isinstance(item.value, ast.Name)
                    and item.value.id == "self"
                ):
                    names.append(item.attr)
    return names


def _self_scene_inputs_accesses(node):
    return [
        child
        for child in ast.walk(node)
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
            and child.attr == "_scene_inputs"
        )
    ]


def test_stage3a_public_entrypoint_exists_and_is_callable():
    assert callable(getattr(MoviePipeline, METHOD, None)), (
        "Stage 3A RED: MoviePipeline.create_scene_generation is missing"
    )


def test_stage3a_signature_has_exact_arguments_and_default_duration():
    method = _future_method(MoviePipeline)
    signature = inspect.signature(method)
    assert list(signature.parameters) == [
        "self",
        "scene_id",
        "scene_data",
        "duration",
    ]
    assert signature.parameters["duration"].default == 5


def test_stage3a_registers_then_composes_once_with_exact_argument_identity():
    spy = BoundarySpy(result=object())
    pipeline = _pipeline_with_spy(spy)
    scene_id = "01"
    scene_data = {"title": "Scene"}
    duration = DurationSentinel()

    result = _future_method(pipeline)(scene_id, scene_data, duration)

    assert result is spy.result
    assert [event[0] for event in spy.events] == ["register", "stage2w"]
    assert spy.events[0][1] is scene_id
    assert spy.events[0][2] is scene_data
    assert spy.events[0][3] is duration
    assert spy.events[1][1] is scene_id
    assert spy.events[1][2] is scene_data
    assert spy.events[1][3] is duration


def test_stage3a_preserves_string_scene_id_distinct_from_integer():
    string_spy = BoundarySpy(result=object())
    integer_spy = BoundarySpy(result=object())
    string_pipeline = _pipeline_with_spy(string_spy)
    integer_pipeline = _pipeline_with_spy(integer_spy)
    scene_data = object()

    _future_method(string_pipeline)("01", scene_data, 7)
    _future_method(integer_pipeline)(1, scene_data, 7)

    assert string_spy.events[0][1] == "01"
    assert string_spy.events[1][1] == "01"
    assert integer_spy.events[0][1] == 1
    assert integer_spy.events[1][1] == 1
    assert string_spy.events[0][1] != integer_spy.events[0][1]
    assert type(string_spy.events[0][1]) is str
    assert type(integer_spy.events[0][1]) is int


def test_stage3a_rejects_scene_id_normalization_and_preserves_identity():
    spy = BoundarySpy(result=object())
    pipeline = _pipeline_with_spy(spy)
    scene_id = SceneIdSentinel()

    _future_method(pipeline)(scene_id, object(), DurationSentinel())

    assert spy.events[0][1] is scene_id
    assert spy.events[1][1] is scene_id


def test_stage3a_default_duration_is_forwarded_as_exact_integer_five():
    spy = BoundarySpy(result=object())
    pipeline = _pipeline_with_spy(spy)
    scene_id = object()
    scene_data = object()

    _future_method(pipeline)(scene_id, scene_data)

    assert spy.events[0][3] == 5
    assert type(spy.events[0][3]) is int
    assert spy.events[1][3] == 5
    assert type(spy.events[1][3]) is int


@pytest.mark.parametrize("result", [{"status": "submitted"}, object()])
def test_stage3a_returns_exact_stage2w_result_object(result):
    spy = BoundarySpy(result=result)
    pipeline = _pipeline_with_spy(spy)

    actual = _future_method(pipeline)(1, object(), 5)

    assert actual is result


def test_stage3a_registration_failure_propagates_without_stage2w_or_retry():
    error = RegistrationError("registration failed")
    spy = BoundarySpy(registration_error=error, result=object())
    pipeline = _pipeline_with_spy(spy)

    with pytest.raises(RegistrationError) as exc_info:
        _future_method(pipeline)("01", object(), object())

    assert exc_info.value is error
    assert [event[0] for event in spy.events] == ["register"]


def test_stage3a_stage2w_failure_propagates_without_wrapper_or_rollback():
    error = Stage2WError("stage2w failed")
    spy = BoundarySpy(stage2w_error=error)
    pipeline = _pipeline_with_spy(spy)

    with pytest.raises(Stage2WError) as exc_info:
        _future_method(pipeline)("01", {"title": "Scene"}, 7)

    assert exc_info.value is error
    assert [event[0] for event in spy.events] == ["register", "stage2w"]


def test_stage3a_real_registration_remains_after_stage2w_failure():
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline._scene_inputs = {}
    error = Stage2WError("downstream failed")

    def stage2w(_scene_id, _scene_data, _duration):
        raise error

    pipeline.create_prepare_submit_scene_generation = stage2w
    scene_id = "01"
    nested = {"camera": "wide"}
    scene_data = {"title": "Original", "nested": nested}
    duration = DurationSentinel()

    with pytest.raises(Stage2WError) as exc_info:
        _future_method(pipeline)(scene_id, scene_data, duration)

    assert exc_info.value is error
    resolved = pipeline._resolve_scene_input(scene_id)
    assert resolved["scene_data"] == scene_data
    assert resolved["scene_data"] is not scene_data
    assert resolved["scene_data"]["nested"] is nested
    assert resolved["duration"] is duration


def test_stage3a_public_entrypoint_does_not_mutate_caller_scene_data():
    spy = BoundarySpy(result=object())
    pipeline = _pipeline_with_spy(spy)
    nested = []
    scene_data = {"title": "Stable", "nested": nested}
    before = dict(scene_data)

    _future_method(pipeline)("01", scene_data, 5)

    assert scene_data == before
    assert scene_data["nested"] is nested


def test_stage3a_repeated_calls_are_independent_and_not_cached():
    first = object()
    second = object()
    spy = BoundarySpy(result=first)
    pipeline = _pipeline_with_spy(spy)

    assert _future_method(pipeline)("A", {"n": 1}, 3) is first
    spy.result = second
    assert _future_method(pipeline)("B", {"n": 2}, 4) is second

    assert first is not second
    assert [event[0] for event in spy.events] == [
        "register",
        "stage2w",
        "register",
        "stage2w",
    ]
    assert spy.events[0][1] == "A"
    assert spy.events[2][1] == "B"


def test_stage3a_changes_only_scene_input_storage_and_not_other_engine_state():
    spy = BoundarySpy(result=object())
    pipeline = _pipeline_with_spy(spy)
    pipeline.queue = object()
    pipeline.video_provider = object()
    pipeline.production_orchestrator = object()
    pipeline.reactive_orchestrator = object()
    marker = object()
    pipeline.marker = marker
    before_keys = set(pipeline.__dict__)
    before_ids = {
        name: id(value)
        for name, value in pipeline.__dict__.items()
        if name != "_scene_inputs"
    }

    _future_method(pipeline)("01", {"title": "Scene"}, 5)

    assert set(pipeline.__dict__) == before_keys
    assert pipeline.marker is marker
    assert {
        name: id(value)
        for name, value in pipeline.__dict__.items()
        if name != "_scene_inputs"
    } == before_ids


def test_stage3a_does_not_call_legacy_create_scene_or_other_pipeline_paths():
    spy = BoundarySpy(result=object())
    pipeline = _pipeline_with_spy(spy)
    calls = []

    def forbidden(name):
        def bomb(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError(f"Stage 3A must not call {name}")
        return bomb

    for name in (
        "create_scene",
        "create_scene_direction",
        "prepare_scene_generation",
        "submit_scene_generation",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
        "_resolve_scene_input",
        "advance_scene_once",
    ):
        setattr(pipeline, name, forbidden(name))

    _future_method(pipeline)("01", object(), 5)

    assert calls == []


def test_stage3a_method_is_bounded_two_boundary_delegation():
    node = _method_ast()
    nodes = list(ast.walk(node))
    assert not any(
        isinstance(
            child,
            (
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
                ast.Match,
                ast.Await,
                ast.Yield,
                ast.YieldFrom,
                ast.Lambda,
                ast.If,
                ast.IfExp,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        )
        for child in nodes
    )

    calls = [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
    ]
    assert len(calls) == 2
    assert all(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
        for call in calls
    )
    assert [call.func.attr for call in calls] == [
        "_register_scene_input",
        "create_prepare_submit_scene_generation",
    ]
    assert _attribute_calls(node).count("_register_scene_input") == 1
    assert _attribute_calls(node).count(
        "create_prepare_submit_scene_generation"
    ) == 1
    forbidden = {
        "create_scene",
        "create_scene_direction",
        "prepare_scene_generation",
        "submit_scene_generation",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
        "_resolve_scene_input",
        "advance_scene_once",
        "process_all",
        "add_task",
        "plan_scene",
        "get",
        "read_text",
        "write_text",
        "sleep",
    }
    assert not (set(_attribute_calls(node)) & forbidden)
    assert not _self_store_names(node)
    assert not _self_scene_inputs_accesses(node)


def test_stage3a_method_does_not_directly_use_providers_queue_or_persistence():
    node = _method_ast()
    names = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
    }
    attributes = {
        child.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Attribute)
    }
    forbidden_names = {
        "GenerationQueue",
        "GenerationTask",
        "ProviderManager",
        "ProviderRouter",
        "ProviderCatalog",
        "ProviderRegistry",
        "Path",
        "open",
        "json",
        "threading",
        "asyncio",
    }
    forbidden_attributes = {
        "provider_manager",
        "provider_router",
        "generation_queue",
        "queue",
        "persist",
        "process_all",
        "add_task",
        "write_text",
        "read_text",
        "mkdir",
        "sleep",
        "backoff",
    }
    assert not (names & forbidden_names)
    assert not (attributes & forbidden_attributes)
