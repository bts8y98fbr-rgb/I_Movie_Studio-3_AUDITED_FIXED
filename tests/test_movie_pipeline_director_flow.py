import json
from pathlib import Path

from core.movie_engine.movie_pipeline import MoviePipeline


def test_movie_pipeline_director_flow(tmp_path):
    project_path = tmp_path / "movie"

    pipeline = MoviePipeline(
        project_path=project_path,
    )

    result = pipeline.create_scene(
        1,
        {
            "visual": "a futuristic city at night",
            "video": "slow cinematic camera movement",
        },
        5,
    )

    assert result["scene_id"] == 1
    assert result["duration"] == 5.0

    assert result["director_file"]

    director_file = Path(
        result["director_file"]
    )

    assert director_file.exists()

    direction = json.loads(
        director_file.read_text(
            encoding="utf-8"
        )
    )

    assert direction["scene_id"] == 1
    assert direction["shot_count"] > 0
    assert len(direction["shots"]) > 0

    timeline = result["timeline"]

    assert len(timeline) == 1
    assert timeline[0]["scene_id"] == 1
    assert timeline[0]["duration"] == 5.0
