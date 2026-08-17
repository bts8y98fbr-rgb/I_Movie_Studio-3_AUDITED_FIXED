def test_project_events_records_generation_events(tmp_path):

    from core.movie_engine.project_events import ProjectEvents


    events = ProjectEvents(
        tmp_path
    )


    created = events.emit(
        "generation_started",
        {
            "scene_id": 1,
            "shot_id": 2,
            "model": "cinematic_video_ultra",
        }
    )


    finished = events.emit(
        "generation_completed",
        {
            "asset_id": "hero001",
            "version": "v001",
        }
    )


    assert (
        created["type"]
        ==
        "generation_started"
    )


    assert (
        len(
            events.get_all()
        )
        ==
        2
    )


    found = events.find(
        "generation_completed"
    )


    assert (
        len(found)
        ==
        1
    )


    assert (
        events.latest()["data"]["asset_id"]
        ==
        "hero001"
    )
