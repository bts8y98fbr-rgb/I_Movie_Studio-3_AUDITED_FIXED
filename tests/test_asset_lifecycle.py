def test_asset_lifecycle_status_flow(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry
    from core.ai_core.asset_lifecycle import AssetLifecycle


    registry = AssetRegistry(
        tmp_path
    )


    registry.register(
        {
            "asset_id": "hero001",
            "type": "video",
            "provider": "Video AI",
            "status": "generated",
            "metadata": {
                "scene_id": 1,
                "shot_id": 1,
            },
        }
    )


    lifecycle = AssetLifecycle(
        registry
    )


    assert (
        lifecycle.get_status(
            "hero001"
        )
        ==
        "generated"
    )


    assert lifecycle.approve(
        "hero001"
    )


    assert (
        lifecycle.get_status(
            "hero001"
        )
        ==
        "approved"
    )


    assert lifecycle.activate(
        "hero001"
    )


    assert (
        lifecycle.get_status(
            "hero001"
        )
        ==
        "active"
    )
