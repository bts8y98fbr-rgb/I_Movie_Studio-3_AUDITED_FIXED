import json
from pathlib import Path
from types import SimpleNamespace

from core.movie_engine.generation_engine import GenerationEngine


class VideoAIRouterStub:
    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return SimpleNamespace(name="Video AI")


def test_generation_preserves_scene_and_shot_identity(tmp_path: Path):
    project = tmp_path / "movie"
    render_plan = project / "render" / "scene_001" / "render_plan.json"
    render_plan.parent.mkdir(parents=True)
    render_plan.write_text(
        json.dumps(
            {
                "scene_id": 1,
                "render_settings": {
                    "resolution": "7680x4320",
                    "fps": 60,
                    "hdr": True,
                    "color_depth": 10,
                },
                "shots": [
                    {
                        "shot_id": 1,
                        "timeline": {"start": 0, "duration": 3.33},
                        "camera": {"shot_type": "wide_establishing"},
                        "director_prompt": "space station wide shot",
                    },
                    {
                        "shot_id": 2,
                        "timeline": {"start": 3.33, "duration": 3.33},
                        "camera": {"shot_type": "hero_reveal"},
                        "director_prompt": "space station hero reveal",
                    },
                    {
                        "shot_id": 3,
                        "timeline": {"start": 6.66, "duration": 3.34},
                        "camera": {"shot_type": "cinematic_close"},
                        "director_prompt": "space station close",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    engine = GenerationEngine(project, "8k")
    engine.provider_router = VideoAIRouterStub()
    result_path = engine.generate_scene(1)
    result = json.loads(Path(result_path).read_text(encoding="utf-8"))

    assert result["status"] == "completed"
    assert result["generated"] == 3

    for expected_shot, task in enumerate(result["tasks"], start=1):
        assert task["metadata"]["scene_id"] == 1
        assert task["metadata"]["shot_id"] == expected_shot
        assert task["metadata"]["timeline"]["duration"] > 0

        asset = task["result"]
        assert asset["metadata"]["scene_id"] == 1
        assert asset["metadata"]["shot_id"] == expected_shot
        assert f"scene_001/shot_{expected_shot:03d}" in asset["asset_path"]
        assert Path(asset["asset_file"]).is_file()
