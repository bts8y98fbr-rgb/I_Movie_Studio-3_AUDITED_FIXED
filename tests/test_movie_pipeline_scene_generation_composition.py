import ast
import inspect
import textwrap

import pytest

from core.movie_engine.movie_pipeline import MoviePipeline


METHOD = "create_prepare_submit_scene_generation"


class SceneIdentitySentinel:
    def _reject(self, operation):
        raise AssertionError(
            f"Stage 2W composition must not {operation} scene_id"
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


class Stage2WError(RuntimeError):
    pass


class CompositionSpy:
    def __init__(
        self,
        *,
        direction_result=None,
        preparation_result=None,
        submission_result=None,
        direction_error=None,
        preparation_error=None,
        submission_error=None,
    ):
        self.direction_result = direction_result
        self.preparation_result = preparation_result
        self.submission_result = submission_result
        self.direction_error = direction_error
        self.preparation_error = preparation_error
        self.submission_error = submission_error
        self.events = []

    def create_scene_direction(self, scene_id, scene_data, duration):
        self.events.append(
            ("direction", scene_id, scene_data, duration)
        )
        if self.direction_error is not None:
            raise self.direction_error
        return self.direction_result

    def prepare_scene_generation(self, scene_id):
        self.events.append(("prepare", scene_id))
        if self.preparation_error is not None:
            raise self.preparation_error
        return self.preparation_result

    def submit_scene_generation(self, scene_id):
        self.events.append(("submit", scene_id))
        if self.submission_error is not None:
            raise self.submission_error
        return self.submission_result


def _future_method(target):
    method = getattr(target, METHOD, None)
    assert callable(method), (
        "Stage 2W RED: "
        "MoviePipeline.create_prepare_submit_scene_generation "
        "is missing"
    )
    return method


def _pipeline_with_spy(spy):
    pipeline = MoviePipeline.__new__(MoviePipeline)
    pipeline.create_scene_direction = spy.create_scene_direction
    pipeline.prepare_scene_generation = spy.prepare_scene_generation
    pipeline.submit_scene_generation = spy.submit_scene_generation
    return pipeline


def _bomb(name):
    def forbidden(*_args, **_kwargs):
        raise AssertionError(
            f"Stage 2W composition must not call {name}"
        )
    return forbidden


def _install_forbidden_paths(pipeline):
    for name in (
        "load_scene_direction",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
    ):
        setattr(pipeline, name, _bomb(name))


def _method_ast():
    method = _future_method(MoviePipeline)
    source = textwrap.dedent(inspect.getsource(method))
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def _called_attributes(node):
    return [
        child.func.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
    ]


def test_stage2w_public_composition_entrypoint_exists():
    assert callable(getattr(MoviePipeline, METHOD, None)), (
        "Stage 2W RED: "
        "MoviePipeline.create_prepare_submit_scene_generation "
        "is missing"
    )


def test_stage2w_signature_has_exact_public_arguments_and_default():
    method = _future_method(MoviePipeline)
    signature = inspect.signature(method)
    parameters = list(signature.parameters.values())

    assert [p.name for p in parameters] == [
        "self",
        "scene_id",
        "scene_data",
        "duration",
    ]

    assert signature.parameters["duration"].default == 5


def test_stage2w_exact_order_identity_and_submission_return():
    scene_id = SceneIdentitySentinel()
    scene_data = object()
    duration = object()
    submission_result = object()

    spy = CompositionSpy(
        direction_result=object(),
        preparation_result=object(),
        submission_result=submission_result,
    )

    pipeline = _pipeline_with_spy(spy)
    _install_forbidden_paths(pipeline)

    actual = _future_method(pipeline)(
        scene_id,
        scene_data,
        duration,
    )

    assert actual is submission_result

    assert spy.events == [
        ("direction", scene_id, scene_data, duration),
        ("prepare", scene_id),
        ("submit", scene_id),
    ]

    assert spy.events[0][1] is scene_id
    assert spy.events[0][2] is scene_data
    assert spy.events[0][3] is duration
    assert spy.events[1][1] is scene_id
    assert spy.events[2][1] is scene_id


def test_stage2w_default_duration_is_forwarded_exactly_as_five():
    scene_id = object()
    scene_data = object()
    submission_result = object()

    spy = CompositionSpy(
        submission_result=submission_result,
    )

    pipeline = _pipeline_with_spy(spy)
    _install_forbidden_paths(pipeline)

    actual = _future_method(pipeline)(
        scene_id,
        scene_data,
    )

    assert actual is submission_result
    assert spy.events[0] == (
        "direction",
        scene_id,
        scene_data,
        5,
    )


def test_stage2w_direction_failure_stops_before_preparation_and_submission():
    error = Stage2WError("stage2w direction failure")
    spy = CompositionSpy(direction_error=error)

    pipeline = _pipeline_with_spy(spy)
    _install_forbidden_paths(pipeline)

    with pytest.raises(Stage2WError) as exc_info:
        _future_method(pipeline)(
            object(),
            object(),
            object(),
        )

    assert exc_info.value is error
    assert [event[0] for event in spy.events] == [
        "direction",
    ]


def test_stage2w_preparation_failure_stops_before_submission():
    error = Stage2WError("stage2w preparation failure")
    spy = CompositionSpy(preparation_error=error)

    pipeline = _pipeline_with_spy(spy)
    _install_forbidden_paths(pipeline)

    with pytest.raises(Stage2WError) as exc_info:
        _future_method(pipeline)(
            object(),
            object(),
            object(),
        )

    assert exc_info.value is error
    assert [event[0] for event in spy.events] == [
        "direction",
        "prepare",
    ]


def test_stage2w_submission_exception_is_propagated_exactly():
    error = Stage2WError("stage2w submission failure")
    spy = CompositionSpy(submission_error=error)

    pipeline = _pipeline_with_spy(spy)
    _install_forbidden_paths(pipeline)

    with pytest.raises(Stage2WError) as exc_info:
        _future_method(pipeline)(
            object(),
            object(),
            object(),
        )

    assert exc_info.value is error
    assert [event[0] for event in spy.events] == [
        "direction",
        "prepare",
        "submit",
    ]


def test_stage2w_does_not_auto_load_direction_or_touch_lifecycle():
    spy = CompositionSpy(
        submission_result=object(),
    )

    pipeline = _pipeline_with_spy(spy)
    _install_forbidden_paths(pipeline)

    _future_method(pipeline)(
        object(),
        object(),
        object(),
    )

    assert [event[0] for event in spy.events] == [
        "direction",
        "prepare",
        "submit",
    ]


def test_stage2w_method_is_exact_bounded_three_bridge_composition():
    node = _method_ast()
    body = list(node.body)

    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]

    assert len(body) == 3
    assert isinstance(body[0], ast.Expr)
    assert isinstance(body[0].value, ast.Call)
    assert isinstance(body[1], ast.Expr)
    assert isinstance(body[1].value, ast.Call)
    assert isinstance(body[2], ast.Return)
    assert isinstance(body[2].value, ast.Call)

    assert _called_attributes(node) == [
        "create_scene_direction",
        "prepare_scene_generation",
        "submit_scene_generation",
    ]


def test_stage2w_contains_no_hidden_control_flow_or_compensation():
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


def test_stage2w_contains_no_direct_component_provider_or_state_access():
    node = _method_ast()

    forbidden_calls = {
        "load_scene_direction",
        "inspect_scene_lifecycle",
        "advance_scene_once",
        "create_scene",
        "regenerate_from_master_prompt",
        "_regenerate_scene_from_master_prompt",
        "analyze_scene",
        "load_direction",
        "create_storyboard_from_director",
        "create_render_plan",
        "generate_scene",
        "process_all",
        "add_task",
        "select",
        "get",
        "read_text",
        "write_text",
        "exists",
        "sleep",
    }

    assert not (
        set(_called_attributes(node))
        & forbidden_calls
    )

    forbidden_names = {
        "AIDirector",
        "StoryboardEngine",
        "ShotRenderer",
        "GenerationEngine",
        "GenerationQueue",
        "ProviderManager",
        "ProviderRouter",
        "ProviderCatalog",
        "ProviderRegistry",
        "ModelPolicy",
        "Path",
        "open",
    }

    used_names = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
    }

    assert not (used_names & forbidden_names)

    attributes = {
        child.attr
        for child in ast.walk(node)
        if isinstance(child, ast.Attribute)
    }

    assert "_scene_inputs" not in attributes


def test_stage2w_does_not_mutate_pipeline_state():
    node = _method_ast()

    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
                ast.NamedExpr,
            ),
        ):
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
                targets = [child.target]
            elif isinstance(child, ast.NamedExpr):
                targets = [child.target]

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
                        "Stage 2W composition must not "
                        "mutate pipeline state"
                    )
