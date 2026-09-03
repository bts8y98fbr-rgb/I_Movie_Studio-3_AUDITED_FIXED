import json
from types import SimpleNamespace


class VideoAIRouterStub:
    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return SimpleNamespace(name="Video AI")


def test_generation_queue_saves_result_through_storage(tmp_path):

    from core.movie_engine.generation_engine import GenerationEngine


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
                "director_prompt": "Storage integration test",
                "timeline": {
                    "duration": 5,
                },
                "camera": {
                    "shot_type": "hero_reveal",
                    "movement": "push_in",
                },
            }
        ],
    }


    (render_dir / "render_plan.json").write_text(
        json.dumps(render_plan),
        encoding="utf-8",
    )


    engine = GenerationEngine(
        project_path=tmp_path,
        quality="8k",
    )
    engine.provider_router = VideoAIRouterStub()


    engine.generate_scene(1)


    asset_file = (
        tmp_path
        / "assets"
        / "video"
        / "scene_001"
        / "shot_001"
        / "asset.json"
    )


    assert asset_file.exists()


    data = json.loads(
        asset_file.read_text(
            encoding="utf-8"
        )
    )


    assert data["type"] == "video"
    assert data["provider"] == "Video AI"

    assert data["metadata"]["scene_id"] == 1
    assert data["metadata"]["shot_id"] == 1

    assert "actual_quality" in data["metadata"]
    assert "shot_model_selection" in data["metadata"]
