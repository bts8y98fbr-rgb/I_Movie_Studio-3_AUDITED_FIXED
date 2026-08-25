def test_project_monitor_reads_generation_state(tmp_path):

    from core.movie_engine.generation_engine import GenerationEngine
    from core.movie_engine.project_monitor import ProjectMonitor


    engine = GenerationEngine(
        project_path=tmp_path,
        quality="8k",
    )


    monitor = ProjectMonitor(
        engine
    )


    state = monitor.get_generation_state()


    assert (
        "timestamp"
        in state
    )


    assert (
        "queue"
        in state
    )


    assert (
        "tasks"
        in state
    )


    active = monitor.get_active_tasks()


    assert (
        isinstance(
            active,
            list
        )
    )
