import json


def test_selected_model_reaches_video_manifest(tmp_path):

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
                "director_prompt": "Hero cinematic reveal",
                "timeline": {
                    "duration": 3,
                },
                "camera": {
                    "shot_type": "hero_reveal",
                    "movement": "push_in",
                },
                "shot_model_selection": {
                    "selected_model": {
                        "name": "cinematic_video_ultra"
                    }
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


    engine.generate_scene(1)


    result = engine.load_result(1)

    task = result["tasks"][0]

    assert task["result"]["model"] is not None

    assert (
        task["result"]["metadata"]["selected_model"]
        is not None
    )
