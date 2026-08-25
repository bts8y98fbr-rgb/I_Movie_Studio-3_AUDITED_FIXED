def test_project_dashboard_returns_project_state(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry
    from core.ai_core.ai_audit_log import AIAuditLog
    from core.movie_engine.project_dashboard import ProjectDashboard


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


    audit = AIAuditLog(
        tmp_path
    )


    audit.record(
        "model_selection",
        {
            "model": {
                "name": "cinematic_video_ultra"
            }
        }
    )


    dashboard = ProjectDashboard(
        registry,
        audit,
    )


    state = dashboard.get_status()


    assert (
        state["project"]["assets"]
        ==
        1
    )


    assert (
        state["providers"]["Video AI"]
        ==
        1
    )


    assert (
        state["models"]["cinematic_video_ultra"]
        ==
        1
    )


    assert (
        state["audit_events"]
        ==
        1
    )
