def test_report_exporter_writes_project_manifest(tmp_path):

    from core.movie_engine.report_exporter import ReportExporter


    exporter = ReportExporter(
        tmp_path
    )


    report = {

        "total_assets":
            3,

        "providers":
            {
                "Video AI": 2,
            },

        "models":
            {
                "cinematic_video_ultra": 2,
            },

    }


    file_path = exporter.export_json(
        report
    )


    assert file_path.exists()


    loaded = exporter.load_json()


    assert (
        loaded["report"]["total_assets"]
        ==
        3
    )


    assert (
        loaded["report"]["providers"]["Video AI"]
        ==
        2
    )
