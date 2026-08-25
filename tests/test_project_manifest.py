def test_project_manifest_creates_project_snapshot(tmp_path):

    from core.movie_engine.project_manifest import ProjectManifest


    manifest_builder = ProjectManifest(
        tmp_path
    )


    manifest = manifest_builder.build(
        {
            "total_assets": 5,
            "providers": {
                "Video AI": 3,
            },
            "models": {
                "cinematic_video_ultra": 3,
            },
        },
        assets=[
            {
                "asset_id": "hero001",
                "version": "v001",
            }
        ],
        audit_summary={
            "events": 10,
        },
    )


    file_path = manifest_builder.save(
        manifest
    )


    assert file_path.exists()


    loaded = manifest_builder.load()


    assert (
        loaded["summary"]["total_assets"]
        ==
        5
    )


    assert (
        loaded["assets"][0]["asset_id"]
        ==
        "hero001"
    )


    assert (
        loaded["audit"]["events"]
        ==
        10
    )
