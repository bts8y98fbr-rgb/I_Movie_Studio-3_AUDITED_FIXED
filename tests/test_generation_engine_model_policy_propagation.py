import json
from types import SimpleNamespace

from core.ai_core.generation_queue import GenerationQueue, GenerationTask
from core.ai_core.model_policy import ModelPolicy, SelectionMode
from core.ai_core.provider_manager import ProviderManager
from core.ai_core.providers.provider_registry import ProviderRegistry
from core.movie_engine.generation_engine import GenerationEngine


class RegisteredBackendRouter:
    def __init__(self, provider_name):
        self.provider_name = provider_name

    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return SimpleNamespace(name=self.provider_name)


def write_render_plan(tmp_path, selected_model_name):
    render_dir = tmp_path / "render" / "scene_001"
    render_dir.mkdir(parents=True)
    render_plan = {
        "scene_id": 1,
        "render_settings": {
            "resolution": "3840x2160",
            "fps": 60,
            "hdr": True,
            "color_depth": 10,
        },
        "shots": [
            {
                "shot_id": 1,
                "director_prompt": "Fixed ModelPolicy propagation test",
                "timeline": {"duration": 1},
                "camera": {},
                "shot_model_selection": {
                    "selected_model": {"name": selected_model_name},
                },
            }
        ],
    }
    (render_dir / "render_plan.json").write_text(
        json.dumps(render_plan),
        encoding="utf-8",
    )


def make_engine_with_backend_spy(tmp_path, monkeypatch, policy):
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
    assert policy.provider == backend.name

    generate_calls = []

    def spy_generate(prompt, **kwargs):
        generate_calls.append((prompt, kwargs))
        return {"status": "success"}

    monkeypatch.setattr(backend, "generate", spy_generate)
    engine.provider_router = RegisteredBackendRouter(backend.name)
    return engine, generate_calls


def test_generation_engine_propagates_fixed_model_policy_mismatch(
    tmp_path,
    monkeypatch,
):
    policy = ModelPolicy(
        provider="Video AI",
        model="requested-model",
        mode=SelectionMode.FIXED,
    )
    write_render_plan(tmp_path, selected_model_name="executed-model")
    engine, generate_calls = make_engine_with_backend_spy(
        tmp_path,
        monkeypatch,
        policy,
    )

    engine.generate_scene(1)

    task = engine.queue.tasks[0]

    assert isinstance(task, GenerationTask)
    assert task.model_policy is policy
    assert generate_calls == []
    assert task.status == "failed"
    assert task.result["status"] == "failed"
    assert "policy" in task.result["error"].lower()
    assert "mismatch" in task.result["error"].lower()


def test_generation_engine_propagates_exact_fixed_model_policy(
    tmp_path,
    monkeypatch,
):
    policy = ModelPolicy(
        provider="Video AI",
        model="requested-model",
        mode=SelectionMode.FIXED,
    )
    write_render_plan(tmp_path, selected_model_name="requested-model")
    engine, generate_calls = make_engine_with_backend_spy(
        tmp_path,
        monkeypatch,
        policy,
    )

    engine.generate_scene(1)

    task = engine.queue.tasks[0]

    assert isinstance(task, GenerationTask)
    assert task.model_policy is policy
    assert len(generate_calls) == 1
    assert task.status == "done"
    assert task.result["status"] == "success"
