def test_asset_registry_enriches_generation_metadata(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry


    registry = AssetRegistry(
        tmp_path
    )


    asset = {

        "asset_id":
            "asset_meta_001",

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

                "hdr":
                    True,
            },

        "routing":
            {
                "fallback_applied":
                    False
            },

        "provider_capabilities":
            {
                "media_types":
                    [
                        "video"
                    ]
            },

        "generation_context":
            {
                "scene_id":
                    1,

                "shot_id":
                    2,

                "shot_profile":
                    "motion",
            },

        "metadata":
            {
                "camera":
                    {
                        "movement":
                            "push_in"
                    }
            },

    }


    result = registry.register(
        asset
    )


    assert result["asset_id"] == (
        "asset_meta_001"
    )


    assert result["model"]["name"] == (
        "cinematic_video_ultra"
    )


    assert result["quality"]["fps"] == 60


    assert result["routing"]["fallback_applied"] is False


    assert result["generation_context"]["shot_id"] == 2


    stored = registry.get_asset(
        "asset_meta_001"
    )


    assert stored is not None


    assert registry.get_versions(
        "asset_meta_001"
    ) == [
        "v001"
    ]
