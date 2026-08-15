import json
from pathlib import Path

from core.movie_engine.movie_compiler import MovieCompiler
from core.movie_engine.export_engine import ExportEngine
from core.movie_engine.export_pipeline import ExportPipeline


def make_render_result(project: Path):
    render_dir = project / "render_output" / "scene_001"
    render_dir.mkdir(parents=True)
    assets = []
    tasks = []

    for shot_id, start in ((1, 0.0), (2, 3.33), (3, 6.67)):
        asset_dir = project / "assets" / "video" / "scene_001" / f"shot_{shot_id:03d}"
        asset_dir.mkdir(parents=True)
        asset_file = asset_dir / f"new_{shot_id}.json"
        asset_file.write_text(json.dumps({"asset_id": f"new-{shot_id}"}), encoding="utf-8")

        result = {
            "asset_id": f"new-{shot_id}",
            "type": "video",
            "asset_file": str(asset_file),
            "metadata": {
                "scene_id": 1,
                "shot_id": shot_id,
                "timeline": {"start": start, "duration": 3.33},
            },
        }
        tasks.append({"task_id": f"task-{shot_id}", "type": "video", "result": result})
        assets.append(result)

    (render_dir / "render_result.json").write_text(
        json.dumps({"scene_id": 1, "generated": 3, "tasks": tasks}),
        encoding="utf-8",
    )


def test_compiler_uses_assets_from_render_result_not_stale_asset_json(tmp_path: Path):
    project = tmp_path / "movie"
    make_render_result(project)

    stale = project / "assets" / "video" / "scene_001" / "shot_001" / "asset.json"
    stale.write_text(json.dumps({
        "asset_id": "stale",
        "type": "video",
        "metadata": {"scene_id": 1, "shot_id": 1, "timeline": {"start": 0, "duration": 3.33}},
    }), encoding="utf-8")

    output = MovieCompiler(project).compile_movie()
    movie = json.loads(Path(output).read_text(encoding="utf-8"))

    assert movie["assets_count"] == 3
    assert {asset["asset_id"] for asset in movie["assets"]} == {"new-1", "new-2", "new-3"}
    assert "stale" not in {asset["asset_id"] for asset in movie["assets"]}
    assert [item["shot_id"] for item in movie["timeline"]] == [1, 2, 3]


def test_export_pipeline_rejects_missing_current_asset_file(tmp_path: Path):
    project = tmp_path / "movie"
    final = project / "final"
    final.mkdir(parents=True)
    movie = {
        "quality": "Master 8K",
        "timeline": [{"scene_id": 1, "shot_id": 1, "start": 0, "duration": 3.33}],
        "assets": [{
            "asset_id": "missing",
            "type": "video",
            "asset_file": str(project / "assets" / "missing.json"),
        }],
        "renders": [{"scene_id": 1}],
    }
    (final / "master_movie.json").write_text(json.dumps(movie), encoding="utf-8")

    plan_path = ExportEngine(project).create_export_plan()
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    assert plan["validation"]["status"] == "failed"

    package_path = ExportPipeline(project).create_export_package()
    package = json.loads(Path(package_path).read_text(encoding="utf-8"))
    assert package["validation"]["status"] == "failed"
    assert any("missing" in error.lower() for error in package["validation"]["errors"])


def test_export_pipeline_accepts_existing_current_assets(tmp_path: Path):
    project = tmp_path / "movie"
    make_render_result(project)
    compiler = MovieCompiler(project)
    compiler.compile_movie()

    ExportEngine(project).create_export_plan()
    package = ExportPipeline(project).create_export_package()
    data = json.loads(Path(package).read_text(encoding="utf-8"))

    assert data["validation"]["status"] == "ready"
    assert len(data["video_tracks"]) == 3
    assert all(track["file_exists"] for track in data["video_tracks"])


def test_render_pipeline_materializes_every_planned_shot(tmp_path: Path):
    from render.render_pipeline import RenderPipeline

    project = tmp_path / "movie"
    plan_dir = project / "render" / "scene_001"
    plan_dir.mkdir(parents=True)
    plan = {
        "scene_id": 1,
        "render_settings": {"resolution": "7680x4320", "fps": 60, "hdr": True, "color_depth": 10},
        "shot_count": 3,
        "shots": [
            {"shot_id": 1, "timeline": {"start": 0, "duration": 3.33}, "camera": {}, "quality": {}},
            {"shot_id": 2, "timeline": {"start": 3.33, "duration": 3.33}, "camera": {}, "quality": {}},
            {"shot_id": 3, "timeline": {"start": 6.66, "duration": 3.34}, "camera": {}, "quality": {}},
        ],
    }
    (plan_dir / "render_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    tasks = []
    for shot_id in (1, 2, 3):
        asset_dir = project / "assets" / "video" / "scene_001" / f"shot_{shot_id:03d}"
        asset_dir.mkdir(parents=True)
        asset_file = asset_dir / f"asset-{shot_id}.json"
        asset_file.write_text(json.dumps({"asset_id": f"asset-{shot_id}"}), encoding="utf-8")
        tasks.append({
            "task_id": f"task-{shot_id}",
            "type": "video",
            "status": "done",
            "metadata": {"scene_id": 1, "shot_id": shot_id},
            "result": {
                "asset_id": f"asset-{shot_id}",
                "type": "video",
                "asset_file": str(asset_file),
                "metadata": {"scene_id": 1, "shot_id": shot_id, "timeline": plan["shots"][shot_id - 1]["timeline"]},
            },
        })
    generation_dir = project / "render_output" / "scene_001"
    generation_dir.mkdir(parents=True)
    (generation_dir / "generation_result.json").write_text(
        json.dumps({"scene_id": 1, "generated": 3, "tasks": tasks}), encoding="utf-8"
    )

    result = Path(RenderPipeline(project).render_plan(plan_dir / "render_plan.json"))
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["shot_count"] == 3
    assert data["rendered"] == 3
    assert data["shot_ids"] == [1, 2, 3]
    for shot_id in (1, 2, 3):
        shot_dir = result.parent / f"shot_{shot_id:03d}"
        assert (shot_dir / "metadata.json").is_file()
        assert (shot_dir / "shot_result.json").is_file()


def test_render_pipeline_rejects_incomplete_generation(tmp_path: Path):
    from render.render_pipeline import RenderPipeline

    project = tmp_path / "movie"
    plan_dir = project / "render" / "scene_001"
    plan_dir.mkdir(parents=True)
    (plan_dir / "render_plan.json").write_text(
        json.dumps({"scene_id": 1, "shots": [{"shot_id": 1}, {"shot_id": 2}, {"shot_id": 3}]}),
        encoding="utf-8",
    )
    generation_dir = project / "render_output" / "scene_001"
    generation_dir.mkdir(parents=True)
    (generation_dir / "generation_result.json").write_text(
        json.dumps({"scene_id": 1, "generated": 2, "tasks": [
            {"type": "video", "status": "done", "metadata": {"shot_id": 1}, "result": {"metadata": {"shot_id": 1}}},
            {"type": "video", "status": "done", "metadata": {"shot_id": 2}, "result": {"metadata": {"shot_id": 2}}},
        ]}),
        encoding="utf-8",
    )
    import pytest
    with pytest.raises(RuntimeError, match="missing shots"):
        RenderPipeline(project).render_plan(plan_dir / "render_plan.json")
