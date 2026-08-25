import json


def test_result_storage_creates_asset_versions(tmp_path):

    from core.ai_core.result_storage import AIResultStorage


    class DummyProvider:

        name = "Video AI"


    class DummyTask:

        task_id = "task001"
        task_type = "video"
        prompt = "cinematic hero shot"
        quality = "8k"
        status = "done"
        provider = DummyProvider()

        metadata = {
            "scene_id": 1,
            "shot_id": 1,
            "shot_model_selection": {
                "selected_model": {
                    "name": "cinematic_video_ultra"
                }
            },
        }

        result = {
            "asset_id": "asset001",
            "type": "video",
        }


    storage = AIResultStorage(
        tmp_path
    )


    first_file = storage.save_result(
        DummyTask()
    )


    assert first_file.exists()


    registry = storage.registry


    assert registry.get_versions(
        "asset001"
    ) == [
        "v001"
    ]


    second_file = storage.save_result(
        DummyTask()
    )


    assert second_file.exists()


    assert registry.get_versions(
        "asset001"
    ) == [
        "v001",
        "v002",
    ]


    assert registry.get_latest_version(
        "asset001"
    ) == "v002"



    version_file = (
        tmp_path
        / "assets"
        / "versions"
        / "asset001"
        / "v001"
        / "asset.json"
    )


    assert version_file.exists()


    data = json.loads(
        version_file.read_text(
            encoding="utf-8"
        )
    )


    assert data["version"] == 1
