def test_asset_version_activation_and_rollback(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry
    from core.ai_core.asset_version_manager import AssetVersionManager


    registry = AssetRegistry(
        tmp_path
    )


    registry.register(
        {
            "asset_id": "hero001",
            "type": "video",
            "provider": "Video AI",
            "model": {
                "name": "cinematic_video_pro"
            },
            "metadata": {
                "scene_id": 1,
                "shot_id": 1,
            },
        }
    )


    registry.create_version(
        "hero001",
        {
            "asset_id": "hero001",
            "type": "video",
            "provider": "Video AI",
            "model": {
                "name": "cinematic_video_ultra"
            },
        }
    )


    manager = AssetVersionManager(
        registry
    )


    assert manager.activate_version(
        "hero001",
        "v002"
    )


    assert (
        manager.get_active_version(
            "hero001"
        )
        ==
        "v002"
    )


    assert manager.rollback(
        "hero001"
    )


    assert (
        manager.get_active_version(
            "hero001"
        )
        ==
        "v001"
    )
