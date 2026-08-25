def test_project_report_builds_project_summary(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry
    from core.movie_engine.project_report import ProjectReport


    registry = AssetRegistry(
        tmp_path
    )


    registry.register(
        {
            "asset_id": "hero001",
            "type": "video",
            "provider": "Video AI",
            "model": {
                "name": "cinematic_video_ultra"
            },
            "metadata": {},
        }
    )


    registry.register(
        {
            "asset_id": "image001",
            "type": "image",
            "provider": "Image AI",
            "model": {
                "name": "image_pro"
            },
            "metadata": {},
        }
    )


    report_builder = ProjectReport(
        registry
    )


    report = report_builder.build()


    assert (
        report["total_assets"]
        ==
        2
    )


    assert (
        report["types"]["video"]
        ==
        1
    )


    assert (
        report["types"]["image"]
        ==
        1
    )


    assert (
        report["providers"]["Video AI"]
        ==
        1
    )


    assert (
        report["models"]["cinematic_video_ultra"]
        ==
        1
    )
