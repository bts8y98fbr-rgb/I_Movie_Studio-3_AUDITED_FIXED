def test_asset_registry_version_management(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry


    registry = AssetRegistry(
        tmp_path
    )


    asset_v1 = {

        "asset_id":
            "hero_asset",

        "type":
            "video",

        "provider":
            "Video AI",

        "model":
            {
                "name":
                    "cinematic_video_pro"
            },

        "quality":
            {
                "resolution":
                    "3840x2160",

                "fps":
                    60,
            },

        "generation_context":
            {
                "scene_id":
                    1,

                "shot_id":
                    1,
            },

    }


    registered_v1 = registry.register(
        asset_v1
    )


    assert registered_v1["version"] == 1


    asset_v2 = {

        "asset_id":
            "hero_asset",

        "type":
            "video",

        "provider":
            "Video AI",

        "model":
            {
                "name":
                    "cinematic_video_ultra"
            },

        "quality":
            {
                "resolution":
                    "7680x4320",

                "fps":
                    60,
            },

        "generation_context":
            {
                "scene_id":
                    1,

                "shot_id":
                    1,
            },

    }


    registered_v2 = registry.register(
        asset_v2
    )


    assert registered_v2["version"] == 2


    versions = registry.get_versions(
        "hero_asset"
    )


    assert versions == [

        "v001",

        "v002",

    ]


    latest = registry.get_latest_version(
        "hero_asset"
    )


    assert latest == "v002"


    stored = registry.get_asset(
        "hero_asset"
    )


    assert stored is not None


    assert (
        stored["model"]["name"]
        ==
        "cinematic_video_ultra"
    )
