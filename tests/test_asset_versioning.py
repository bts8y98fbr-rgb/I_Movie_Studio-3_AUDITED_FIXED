def test_asset_registry_version_management(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry


    registry = AssetRegistry(
        tmp_path
    )


    first = registry.register(
        {
            "asset_id": "video001",
            "type": "video",
            "provider": "Video AI",
            "metadata": {
                "scene_id": 1,
                "shot_id": 1,
            },
        }
    )


    assert first["version"] == 1

    assert registry.get_versions(
        "video001"
    ) == [
        "v001"
    ]


    second = registry.create_version(
        "video001",
        {
            "asset_id": "video001",
            "type": "video",
            "provider": "Video AI",
            "metadata": {
                "scene_id": 1,
                "shot_id": 1,
            },
            "model": {
                "name": "cinematic_video_ultra"
            },
        }
    )


    assert second == "v002"


    assert registry.get_versions(
        "video001"
    ) == [
        "v001",
        "v002",
    ]


    assert registry.get_latest_version(
        "video001"
    ) == "v002"
