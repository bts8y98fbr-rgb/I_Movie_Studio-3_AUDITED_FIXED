import json
from types import SimpleNamespace

import pytest


class FakeProviderRouter:
    def __init__(self):
        self.routed_provider = SimpleNamespace(name="PixVerse")

    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return self.routed_provider


class FakeExecutionProvider:
    def __init__(self, name):
        self.name = name

    def capabilities(self):
        return {
            "resolutions": ["3840x2160"],
            "fps": [60],
            "hdr": [True],
            "color_depth": [10],
        }

    def generate(self, prompt, **kwargs):
        return {
            "status": "success",
            "provider": self.name,
        }


class SpyProviderManager:
    def __init__(self, backend_available=True):
        self.backend_available = backend_available
        self.get_calls = []
        self.providers = {}

    def get(self, name):
        self.get_calls.append(name)
        if not self.backend_available:
            return None
        if name not in self.providers:
            self.providers[name] = FakeExecutionProvider(name)
        return self.providers[name]


def write_render_plan(tmp_path):
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
                "director_prompt": "Provider identity boundary test",
                "timeline": {"duration": 1},
                "camera": {},
            }
        ],
    }

    (render_dir / "render_plan.json").write_text(
        json.dumps(render_plan),
        encoding="utf-8",
    )


def test_routed_provider_identity_reaches_execution_boundary(tmp_path):
    from core.movie_engine.generation_engine import GenerationEngine

    write_render_plan(tmp_path)

    engine = GenerationEngine(project_path=tmp_path, quality="4k")
    fake_router = FakeProviderRouter()
    spy_manager = SpyProviderManager()
    engine.provider_router = fake_router
    engine.provider_manager = spy_manager

    engine.generate_scene(1)

    routed_provider_name = fake_router.routed_provider.name
    execution_provider_name = spy_manager.get_calls[-1]
    task_provider_name = engine.queue.tasks[0].provider.name

    assert execution_provider_name == task_provider_name
    assert routed_provider_name == execution_provider_name


def test_missing_routed_backend_fails_before_task_creation(
    tmp_path,
    monkeypatch,
):
    import core.movie_engine.generation_engine as generation_engine

    write_render_plan(tmp_path)

    engine = generation_engine.GenerationEngine(
        project_path=tmp_path,
        quality="4k",
    )
    fake_router = FakeProviderRouter()
    spy_manager = SpyProviderManager(backend_available=False)
    engine.provider_router = fake_router
    engine.provider_manager = spy_manager

    task_creation_attempts = []

    def record_task_creation(*args, **kwargs):
        task_creation_attempts.append((args, kwargs))
        raise AssertionError("GenerationTask must not be created")

    monkeypatch.setattr(
        generation_engine,
        "GenerationTask",
        record_task_creation,
    )

    with pytest.raises(RuntimeError, match="PixVerse"):
        engine.generate_scene(1)

    assert spy_manager.get_calls == ["PixVerse"]
    assert task_creation_attempts == []
    assert engine.queue.tasks == []
    assert engine.queue.queue.empty()
