def test_dashboard_api_returns_json_project_state(tmp_path):

    from core.ai_core.asset_registry import AssetRegistry
    from core.movie_engine.project_dashboard import ProjectDashboard
    from core.movie_engine.dashboard_api import DashboardAPI


    registry = AssetRegistry(
        tmp_path
    )


    registry.register(
        {
            "asset_id":
                "hero001",

            "type":
                "video",

            "provider":
                "Video AI",

            "model":
                {
                    "name":
                        "cinematic_video_ultra"
                },

            "metadata":
                {},
        }
    )


    dashboard = ProjectDashboard(
        registry
    )


    api = DashboardAPI(
        dashboard
    )


    response = api.get_project_status()


    assert (
        response["success"]
        is True
    )


    assert (
        response["data"]["project"]["assets"]
        ==
        1
    )


    exported = api.export_json()


    assert (
        '"success": true'
        in exported
    )
