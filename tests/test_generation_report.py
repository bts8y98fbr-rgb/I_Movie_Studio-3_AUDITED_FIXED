def test_generation_report_builds_full_asset_report(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry
    from core.ai_core.ai_audit_log import AIAuditLog
    from core.ai_core.asset_lifecycle import AssetLifecycle
    from core.ai_core.asset_version_manager import AssetVersionManager
    from core.ai_core.generation_report import GenerationReport


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
            "generation_context": {
                "scene_id": 1,
                "shot_id": 5,
            },
            "metadata": {},
        }
    )


    audit = AIAuditLog(
        tmp_path
    )


    audit.record(
        "model_selection",
        {
            "shot_id": 5,
            "model": {
                "name": "cinematic_video_ultra"
            },
        }
    )


    lifecycle = AssetLifecycle(
        registry
    )


    versions = AssetVersionManager(
        registry
    )


    versions.activate_version(
        "hero001",
        "v001"
    )


    report_builder = GenerationReport(
        registry,
        audit,
        lifecycle,
        versions,
    )


    report = report_builder.build(
        "hero001"
    )


    assert report is not None

    assert (
        report["asset_id"]
        ==
        "hero001"
    )

    assert (
        report["active_version"]
        ==
        "v001"
    )

    assert len(
        report["audit_events"]
    ) == 1
