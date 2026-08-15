from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class RenderPipeline:
    """Materialize a render plan into deterministic per-shot render manifests.

    This project currently produces JSON media manifests rather than real video
    frames. The pipeline is nevertheless strict about identity and completeness:
    every shot in the render plan must have a corresponding generated asset and
    every generated asset must produce a shot_result.json + metadata.json.
    """

    def __init__(self, project_path: str | Path = "projects/test_movie"):
        self.project_path = Path(project_path)
        self.render_output = self.project_path / "render_output"
        self.render_output.mkdir(parents=True, exist_ok=True)
        self.export_path = self.project_path / "exports"
        self.export_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        if path.exists():
            return path
        return self.project_path / path

    def _generation_result_path(self, scene_id: int) -> Path:
        return self.render_output / f"scene_{scene_id:03d}" / "generation_result.json"

    def render_plan(self, plan_path: str | Path) -> str:
        plan_path = Path(plan_path)
        if not plan_path.exists():
            raise FileNotFoundError(f"Render plan not found: {plan_path}")

        plan = self._read_json(plan_path)
        scene_id = int(plan["scene_id"])
        shots = plan.get("shots", [])
        expected_ids = [int(shot["shot_id"]) for shot in shots]
        if len(expected_ids) != len(set(expected_ids)):
            raise ValueError("Render plan contains duplicate shot_id values")

        generation_path = self._generation_result_path(scene_id)
        if not generation_path.exists():
            raise FileNotFoundError(
                f"Generation result not found: {generation_path}. Run generation first."
            )

        generation = self._read_json(generation_path)
        tasks = generation.get("tasks", [])
        generated_by_shot: dict[int, dict[str, Any]] = {}
        for task in tasks:
            if task.get("type") != "video" or task.get("status") != "done":
                continue
            result = task.get("result") or {}
            metadata = result.get("metadata") or task.get("metadata") or {}
            shot_id = metadata.get("shot_id", task.get("metadata", {}).get("shot_id"))
            if shot_id is None:
                continue
            generated_by_shot[int(shot_id)] = {"task": task, "result": result}

        missing = [shot_id for shot_id in expected_ids if shot_id not in generated_by_shot]
        if missing:
            raise RuntimeError(
                f"Generation is incomplete for scene {scene_id}: missing shots {missing}"
            )

        extra = sorted(set(generated_by_shot) - set(expected_ids))
        if extra:
            raise RuntimeError(
                f"Generation contains unexpected shots for scene {scene_id}: {extra}"
            )

        scene_output = self.render_output / f"scene_{scene_id:03d}"
        scene_output.mkdir(parents=True, exist_ok=True)
        rendered_tasks = []

        for shot in shots:
            shot_id = int(shot["shot_id"])
            generated = generated_by_shot[shot_id]
            task = generated["task"]
            result = generated["result"]
            asset_file = result.get("asset_file")
            resolved_asset = self._resolve(asset_file) if asset_file else None
            if not resolved_asset or not resolved_asset.is_file():
                raise FileNotFoundError(
                    f"Generated asset for scene {scene_id} shot {shot_id} not found: {asset_file}"
                )

            shot_output = scene_output / f"shot_{shot_id:03d}"
            metadata = {
                "scene_id": scene_id,
                "shot_id": shot_id,
                "timeline": shot.get("timeline", {}),
                "camera": shot.get("camera", {}),
                "quality": shot.get("quality", plan.get("render_settings", {})),
                "source_asset_id": result.get("asset_id"),
                "source_asset_file": str(asset_file),
                "resolved_asset_file": str(resolved_asset),
                "status": "prepared",
            }
            shot_result = {
                "scene_id": scene_id,
                "shot_id": shot_id,
                "asset": result,
                "status": "prepared",
                "created": datetime.now().isoformat(),
            }
            self._write_json(shot_output / "metadata.json", metadata)
            self._write_json(shot_output / "shot_result.json", shot_result)

            rendered_tasks.append(
                {
                    "task_id": task.get("task_id"),
                    "type": task.get("type"),
                    "prompt": task.get("prompt"),
                    "provider": task.get("provider"),
                    "quality": task.get("quality"),
                    "status": "rendered",
                    "result": result,
                    "output": task.get("output"),
                    "metadata": task.get("metadata", {}),
                    "render_output": str(shot_output),
                }
            )

        render_result = {
            "scene_id": scene_id,
            "created": datetime.now().isoformat(),
            "quality": plan.get("render_settings", {}),
            "pipeline": "AI Generation Pipeline",
            "render_plan": str(plan_path),
            "generation_file": str(generation_path),
            "shot_count": len(expected_ids),
            "rendered": len(rendered_tasks),
            "shot_ids": expected_ids,
            "tasks": rendered_tasks,
            "status": "rendered_manifest",
        }
        result_file = scene_output / "render_result.json"
        self._write_json(result_file, render_result)
        return str(result_file)

    def render(self, timeline):
        """Backward-compatible export-manifest helper for legacy callers."""
        filename = f"movie_project_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        target = self.export_path / filename
        self._write_json(
            target,
            {"status": "prepared", "timeline": timeline, "created": datetime.now().isoformat()},
        )
        return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an AI Movie Studio render plan")
    parser.add_argument("render_plan", help="Path to render_plan.json")
    args = parser.parse_args()
    result = RenderPipeline().render_plan(args.render_plan)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
