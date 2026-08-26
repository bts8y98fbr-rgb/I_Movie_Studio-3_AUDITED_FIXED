from core.ai_core.orchestration.reactive_orchestrator import ReactiveOrchestrator


def test_prompt_change_creates_revision_and_regenerates_only_selected_scenes():
    submitted = []

    def submit_scene(scene_id, prompt):
        submitted.append((scene_id, prompt))
        return {"status": "submitted"}

    orchestrator = ReactiveOrchestrator(submit_scene=submit_scene)

    result = orchestrator.apply(
        "A darker cinematic version with a slower camera movement",
        [2, 4],
    )

    assert result["revision"] == 1
    assert result["status"] == "submitted"
    assert result["affected_scene_ids"] == [2, 4]
    assert [item[0] for item in submitted] == [2, 4]
    assert all("darker cinematic" in item[1] for item in submitted)


def test_prompt_changes_get_distinct_revisions():
    orchestrator = ReactiveOrchestrator()

    first = orchestrator.apply("Version one", [1])
    second = orchestrator.apply("Version two", [1])

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert first["prompt_fingerprint"] != second["prompt_fingerprint"]
