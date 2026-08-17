def test_generation_queue_emits_events(tmp_path):

    from core.ai_core.generation_queue import GenerationQueue, GenerationTask
    from core.movie_engine.project_events import ProjectEvents


    class Provider:

        name = "Video AI"


        def generate(
            self,
            *args,
            **kwargs
        ):

            return {
                "asset_id":
                    "hero001",

                "type":
                    "video",
            }



    queue = GenerationQueue()


    task = GenerationTask(
        "video",
        "hero shot",
        Provider(),
        project_path=tmp_path,
        metadata={
            "scene_id": 1,
            "shot_id": 1,
        },
    )


    queue.add_task(
        task
    )


    result = queue.process_next()


    assert (
        result.status
        ==
        "done"
    )


    events = ProjectEvents(
        tmp_path
    )


    assert len(
        events.find(
            "generation_started"
        )
    ) == 1


    assert len(
        events.find(
            "generation_completed"
        )
    ) == 1
