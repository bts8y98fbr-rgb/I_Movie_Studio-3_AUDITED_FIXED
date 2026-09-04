import json
from types import SimpleNamespace

from core.ai_core.generation_queue import GenerationQueue, GenerationTask
from core.ai_core.model_policy import ModelPolicy, SelectionMode
from core.ai_core.model_router import ModelRouter
from core.ai_core.provider_manager import ProviderManager
from core.ai_core.providers.provider_registry import ProviderRegistry
from core.ai_core.quality_policy import QualityPolicy
from core.ai_core.shot_model_selector import ShotModelSelector
from core.movie_engine.generation_engine import GenerationEngine
from core.movie_engine.shot_renderer import ShotRenderer


ROUTING_DIAGNOSTIC_KEYS = {
    "status",
    "requested_quality",
    "actual_quality",
    "fallback_applied",
    "notification",
    "time",
}


class RegisteredVideoAIRouter:
    def __init__(self, provider_name):
        self.provider_name = provider_name

    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return SimpleNamespace(name=self.provider_name)


def test_selected_model_schema_is_canonical_through_generation(
    tmp_path,
    monkeypatch,
):
    deterministic_model = {
        "name": "requested-model",
        "type": "video",
        "quality": 10,
        "motion": 10,
        "realism": 10,
        "detail": 10,
        "profiles": ["cinematic", "environment", "motion", "detail"],
        "resolutions": ["3840x2160"],
        "fps": [60],
        "hdr": [True],
        "color_depth": [10],
    }

    storyboard_dir = tmp_path / "storyboard" / "scene_001"
    storyboard_dir.mkdir(parents=True)
    (storyboard_dir / "storyboard.json").write_text(
        json.dumps(
            {
                "scene_id": 1,
                "shots": [
                    {
                        "shot_id": 1,
                        "duration": 1,
                        "camera": {
                            "shot_type": "wide_establishing",
                            "movement": "slow_pan",
                        },
                        "director_prompt": "Canonical model schema test",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    renderer = ShotRenderer(project_path=tmp_path, quality="4k")
    assert isinstance(renderer.quality_policy, QualityPolicy)
    assert isinstance(renderer.model_router, ModelRouter)
    assert isinstance(renderer.shot_selector, ShotModelSelector)
    assert renderer.shot_selector.model_router is renderer.model_router

    renderer.model_router.models["video"] = [deterministic_model]
    expected_router_result = renderer.model_router.get_best_model(
        "video",
        shot_context={"profile": "environment"},
    )
    assert expected_router_result["status"] == "approved"

    render_plan_path = renderer.create_render_plan(1)
    render_plan = json.loads(render_plan_path.read_text(encoding="utf-8"))

    shot_model_selection = render_plan["shots"][0]["shot_model_selection"]
    selected_model = shot_model_selection["selected_model"]
    canonical_flat_name = selected_model.get("name")
    routing_diagnostics = shot_model_selection["routing_diagnostics"]

    policy = ModelPolicy(
        provider="Video AI",
        model="requested-model",
        mode=SelectionMode.FIXED,
    )
    engine = GenerationEngine(
        project_path=tmp_path,
        quality="4k",
        model_policy=policy,
    )
    assert isinstance(engine.provider_manager, ProviderManager)
    assert isinstance(engine.provider_manager.registry, ProviderRegistry)
    assert isinstance(engine.queue, GenerationQueue)

    backend = engine.provider_manager.get("Video AI")
    assert backend is not None
    assert backend.name == policy.provider

    provider_calls = []

    def spy_generate(prompt, **kwargs):
        provider_calls.append((prompt, kwargs))
        return {"status": "success"}

    monkeypatch.setattr(backend, "generate", spy_generate)
    engine.provider_router = RegisteredVideoAIRouter(backend.name)

    engine.generate_scene(1)

    task = engine.queue.tasks[0]
    assert isinstance(task, GenerationTask)

    assert canonical_flat_name == "requested-model"
    assert "selected_model" not in selected_model
    assert set(routing_diagnostics) == ROUTING_DIAGNOSTIC_KEYS
    for key in ROUTING_DIAGNOSTIC_KEYS - {"time"}:
        assert routing_diagnostics[key] == expected_router_result.get(key)
    assert isinstance(routing_diagnostics["time"], str)

    assert task.model_policy is policy
    assert len(provider_calls) == 1
    assert task.status == "done"
    assert task.result["status"] == "success"
