def test_asset_registry_query_api(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry


    registry = AssetRegistry(
        tmp_path
    )


    registry.register(
        {
            "asset_id": "abc123",
            "type": "video",
            "provider": "Video AI",
            "metadata": {
                "scene_id": 1,
                "shot_id": 2,
            },
        }
    )


    registry.register(
        {
            "asset_id": "img001",
            "type": "image",
            "provider": "Image AI",
            "metadata": {
                "scene_id": 2,
                "shot_id": 3,
            },
        }
    )


    assert (
        registry.get_asset("abc123")
        is not None
    )


    assert len(
        registry.find_by_scene(1)
    ) == 1


    assert len(
        registry.find_by_shot(2)
    ) == 1


    assert len(
        registry.find_by_type("video")
    ) == 1


    assert registry.remove_asset(
        "abc123"
    )


    assert (
        registry.get_asset("abc123")
        is None
    )
