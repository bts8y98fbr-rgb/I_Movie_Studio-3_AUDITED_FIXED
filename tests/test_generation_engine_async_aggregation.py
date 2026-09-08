import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.movie_engine.generation_engine as generation_engine_module
from core.movie_engine.generation_engine import GenerationEngine


class VideoAIRouterStub:
    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return SimpleNamespace(name="Video AI")


class ControlledQueue:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.tasks = []

    def add_task(self, task):
        self.tasks.append(task)
        return task

    def process_all(self):
        assert len(self.tasks) == len(self.statuses)

        for task, status in zip(self.tasks, self.statuses):
            task.status = status
            task.result = {
                "status": status,
                "synthetic_stage_2i_red": True,
            }

        return list(self.tasks)

    def get_status(self):
        return [
            {
                "task_id": task.task_id,
                "type": task.task_type,
                "status": task.status,
                "metadata": task.metadata,
                "result": task.result,
                "provider": getattr(task.provider, "name", None),
                "quality": task.quality,
                "output": task.output,
            }
            for task in self.tasks
        ]


def write_render_plan(project_path: Path, shot_count: int):
    render_dir = project_path / "render" / "scene_001"
    render_dir.mkdir(parents=True)

    shots = [
        {
            "shot_id": index,
            "director_prompt": f"Stage 2I aggregation shot {index}",
            "timeline": {
                "start": index - 1,
                "duration": 1,
            },
            "camera": {},
        }
        for index in range(1, shot_count + 1)
    ]

    render_plan = {
        "scene_id": 1,
        "render_settings": {
            "resolution": "3840x2160",
            "fps": 60,
            "hdr": True,
            "color_depth": 10,
        },
        "shots": shots,
    }

    (render_dir / "render_plan.json").write_text(
        json.dumps(render_plan),
        encoding="utf-8",
    )


def generate_with_statuses(tmp_path, monkeypatch, statuses):
    statuses = list(statuses)

    monkeypatch.setattr(
        generation_engine_module,
        "GenerationQueue",
        lambda: ControlledQueue(statuses),
    )

    write_render_plan(tmp_path, len(statuses))

    engine = GenerationEngine(
        project_path=tmp_path,
        quality="4k",
    )
    engine.provider_router = VideoAIRouterStub()

    result_path = Path(engine.generate_scene(1))
    result = json.loads(result_path.read_text(encoding="utf-8"))

    return result


@pytest.mark.parametrize(
    (
        "statuses",
        "expected_scene_status",
        "expected_counts",
    ),
    [
        (
            ["done", "done"],
            "completed",
            {
                "generated": 2,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 0,
            },
        ),
        (
            ["submitted", "submitted"],
            "pending",
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 2,
                "running": 0,
                "pending": 2,
            },
        ),
        (
            ["done", "submitted"],
            "pending",
            {
                "generated": 1,
                "failed": 0,
                "cancelled": 0,
                "submitted": 1,
                "running": 0,
                "pending": 1,
            },
        ),
        (
            ["done", "failed"],
            "completed_with_errors",
            {
                "generated": 1,
                "failed": 1,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 0,
            },
        ),
        (
            ["failed", "submitted"],
            "pending",
            {
                "generated": 0,
                "failed": 1,
                "cancelled": 0,
                "submitted": 1,
                "running": 0,
                "pending": 1,
            },
        ),
        (
            ["running"],
            "pending",
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 1,
                "pending": 1,
            },
        ),
        (
            ["waiting"],
            "pending",
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
            },
        ),
        (
            ["processing"],
            "pending",
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
            },
        ),
        (
            ["provider_weird_state"],
            "pending",
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
            },
        ),
        (
            ["succeeded"],
            "pending",
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 1,
            },
        ),
        (
            ["done", "cancelled"],
            "completed_with_errors",
            {
                "generated": 1,
                "failed": 0,
                "cancelled": 1,
                "submitted": 0,
                "running": 0,
                "pending": 0,
            },
        ),
        (
            ["failed", "cancelled"],
            "completed_with_errors",
            {
                "generated": 0,
                "failed": 1,
                "cancelled": 1,
                "submitted": 0,
                "running": 0,
                "pending": 0,
            },
        ),
        (
            [],
            "pending",
            {
                "generated": 0,
                "failed": 0,
                "cancelled": 0,
                "submitted": 0,
                "running": 0,
                "pending": 0,
            },
        ),
    ],
    ids=[
        "all-done",
        "all-submitted",
        "done-plus-submitted",
        "done-plus-failed",
        "failed-plus-submitted",
        "running",
        "waiting",
        "processing",
        "unknown-state",
        "remote-succeeded-is-not-local-done",
        "done-plus-cancelled",
        "failed-plus-cancelled",
        "empty-scene",
    ],
)
def test_generation_engine_scene_aggregation_contract(
    tmp_path,
    monkeypatch,
    statuses,
    expected_scene_status,
    expected_counts,
):
    result = generate_with_statuses(
        tmp_path,
        monkeypatch,
        statuses,
    )

    assert result["status"] == expected_scene_status

    for field, expected_value in expected_counts.items():
        assert result[field] == expected_value

    assert [
        task["status"]
        for task in result["tasks"]
    ] == statuses

    assert not (tmp_path / "assets" / "registry.json").exists()
    assert list(tmp_path.rglob("asset.json")) == []
