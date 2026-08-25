def test_ai_audit_log_records_model_decision(tmp_path):

    from core.ai_core.ai_audit_log import AIAuditLog


    audit = AIAuditLog(
        tmp_path
    )


    audit.record(
        "model_selection",
        {
            "scene_id": 1,
            "shot_id": 2,
            "model": {
                "name": "cinematic_video_ultra"
            },
            "provider": "Video AI",
            "quality": "8k",
        }
    )


    audit.record(
        "generation_complete",
        {
            "scene_id": 1,
            "shot_id": 2,
            "asset_id": "hero001",
            "version": "v001",
        }
    )


    entries = audit.get_all()


    assert len(
        entries
    ) == 2


    shots = audit.find_by_shot(
        2
    )


    assert len(
        shots
    ) == 1


    models = audit.find_by_model(
        "cinematic_video_ultra"
    )


    assert len(
        models
    ) == 1


    assert (
        models[0]["data"]["provider"]
        ==
        "Video AI"
    )
