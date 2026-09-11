import ast
from pathlib import Path

from core.ai_core.orchestration.reactive_orchestrator import (
    ReactiveOrchestrator,
)


SOURCE_PATH = Path(
    "core/ai_core/orchestration/reactive_orchestrator.py"
)


class OpaqueSceneId:
    def __init__(self, value):
        self.value = value

    def __hash__(self):
        return hash((type(self), self.value))

    def __eq__(self, other):
        return (
            isinstance(other, OpaqueSceneId)
            and self.value == other.value
        )

    def __repr__(self):
        return f"OpaqueSceneId({self.value!r})"


def test_stage2za_numeric_string_scene_id_reaches_callback_unchanged():
    submitted = []
    prompt = "reactive exact identity"

    def submit_scene(scene_id, received_prompt):
        submitted.append((scene_id, received_prompt))
        return {"status": "submitted"}

    orchestrator = ReactiveOrchestrator(
        submit_scene=submit_scene
    )

    result = orchestrator.apply(
        prompt,
        ["01"],
    )

    assert submitted == [("01", prompt)]
    assert result["affected_scene_ids"] == ["01"]


def test_stage2za_string_and_integer_scene_ids_remain_distinct():
    submitted = []

    def submit_scene(scene_id, prompt):
        submitted.append(scene_id)
        return {"status": "submitted"}

    orchestrator = ReactiveOrchestrator(
        submit_scene=submit_scene
    )

    result = orchestrator.apply(
        "preserve types",
        ["1", 1],
    )

    assert submitted == ["1", 1]
    assert result["affected_scene_ids"] == ["1", 1]


def test_stage2za_preserves_first_occurrence_order_without_sorting():
    submitted = []
    scene_ids = [4, "01", 2]

    def submit_scene(scene_id, prompt):
        submitted.append(scene_id)
        return {"status": "submitted"}

    orchestrator = ReactiveOrchestrator(
        submit_scene=submit_scene
    )

    result = orchestrator.apply(
        "preserve caller order",
        scene_ids,
    )

    assert submitted == scene_ids
    assert result["affected_scene_ids"] == scene_ids


def test_stage2za_supports_hashable_non_numeric_scene_ids_and_deduplicates():
    first = OpaqueSceneId("first")
    second = OpaqueSceneId("second")
    duplicate_first = OpaqueSceneId("first")

    submitted = []

    def submit_scene(scene_id, prompt):
        submitted.append(scene_id)
        return {"status": "submitted"}

    orchestrator = ReactiveOrchestrator(
        submit_scene=submit_scene
    )

    result = orchestrator.apply(
        "opaque identifiers",
        [first, second, duplicate_first],
    )

    assert submitted == [first, second]
    assert result["affected_scene_ids"] == [
        first,
        second,
    ]


def test_stage2za_deduplication_keeps_first_occurrence_order():
    submitted = []

    def submit_scene(scene_id, prompt):
        submitted.append(scene_id)
        return {"status": "submitted"}

    orchestrator = ReactiveOrchestrator(
        submit_scene=submit_scene
    )

    result = orchestrator.apply(
        "deduplicate without sorting",
        ["01", 4, "01", 2, 4],
    )

    assert submitted == ["01", 4, 2]
    assert result["affected_scene_ids"] == [
        "01",
        4,
        2,
    ]


def test_stage2za_reactive_job_preserves_exact_scene_id():
    orchestrator = ReactiveOrchestrator(
        submit_scene=lambda scene_id, prompt: {
            "status": "submitted",
            "provider_receipt": "receipt-1",
        }
    )

    result = orchestrator.apply(
        "job identity",
        ["01"],
    )

    assert result["jobs"][0]["scene_id"] == "01"
    assert result["jobs"][0]["status"] == "submitted"
    assert result["jobs"][0]["provider_receipt"] == "receipt-1"


def test_stage2za_callback_failure_keeps_existing_failure_semantics_and_exact_id():
    submitted = []

    def submit_scene(scene_id, prompt):
        submitted.append((scene_id, prompt))
        raise RuntimeError("stage2za-callback-failure")

    orchestrator = ReactiveOrchestrator(
        submit_scene=submit_scene
    )

    result = orchestrator.apply(
        "failure semantics",
        ["01"],
    )

    assert submitted == [
        ("01", "failure semantics")
    ]
    assert result["affected_scene_ids"] == ["01"]
    assert result["status"] == "failed"
    assert result["last_error"] == (
        "stage2za-callback-failure"
    )


def test_stage2za_apply_contains_no_scene_id_normalization_sorting_or_forbidden_layers():
    source = SOURCE_PATH.read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    apply_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.name == "apply"
    )

    direct_call_names = {
        node.func.id
        for node in ast.walk(apply_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }

    attribute_names = {
        node.attr
        for node in ast.walk(apply_node)
        if isinstance(node, ast.Attribute)
    }

    assert "int" not in direct_call_names
    assert "sorted" not in direct_call_names

    forbidden_attributes = {
        "_scene_inputs",
        "_resolve_scene_input",
        "_register_scene_input",
        "create_scene",
        "create_prepare_submit_scene_generation",
        "submit_scene_generation",
        "inspect_scene_lifecycle",
        "advance_scene_once",
    }

    assert forbidden_attributes.isdisjoint(
        attribute_names
    )
