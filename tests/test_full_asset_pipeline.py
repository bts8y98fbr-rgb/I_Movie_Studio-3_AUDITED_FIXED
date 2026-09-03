import json
from types import SimpleNamespace


class VideoAIRouterStub:
    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return SimpleNamespace(name="Video AI")


def test_full_generation_asset_pipeline(tmp_path):

    from core.movie_engine.generation_engine import GenerationEngine


    render_dir = (
        tmp_path
        / "render"
        / "scene_001"
    )

    render_dir.mkdir(
        parents=True
    )


    render_plan = {

        "scene_id":
            1,

        "render_settings":
            {
                "resolution":
                    "7680x4320",

                "fps":
                    60,

                "hdr":
                    True,

                "color_depth":
                    10,
            },

        "shots":
            [

                {

                    "shot_id":
                        1,

                    "director_prompt":
                        "Epic hero reveal shot",

                    "timeline":
                        {
                            "duration":
                                5,
                        },

                    "camera":
                        {
                            "shot_type":
                                "hero_reveal",

                            "movement":
                                "push_in",
                        },

                }

            ]

    }


    (
        render_dir
        / "render_plan.json"
    ).write_text(
        json.dumps(
            render_plan
        ),
        encoding="utf-8",
    )


    engine = GenerationEngine(
        project_path=tmp_path,
        quality="8k",
    )
    engine.provider_router = VideoAIRouterStub()


    result = engine.generate_scene(
        1
    )


    assert result is not None


    registry_files = list(
        (
            tmp_path
            / "assets"
        ).rglob(
            "registry.json"
        )
    )


    assert registry_files


    registry = json.loads(
        registry_files[0].read_text(
            encoding="utf-8"
        )
    )


    assert len(registry) == 1


    asset = registry[0]


    assert asset["type"] == "video"


    assert asset["provider"] is not None


    assert "model" in asset


    assert "quality" in asset


    assert "generation_context" in asset


    version_files = list(
        (
            tmp_path
            / "assets"
        ).rglob(
            "versions"
        )
    )


    assert version_files
