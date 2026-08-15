from datetime import datetime
import json
from pathlib import Path


class MovieCompiler:
    """Compile the latest generated assets referenced by render results.

    The compiler deliberately does not scan ``asset.json`` manifests in shot
    directories because those files can belong to an older generation run.
    Render results are the source of truth for the current generation/render
    chain and contain the exact asset file produced by each task.
    """

    def __init__(self, project_path="projects/test_movie"):
        self.project_path = Path(project_path)
        self.assets_path = self.project_path / "assets"
        self.render_path = self.project_path / "render_output"
        self.final_path = self.project_path / "final"
        self.final_path.mkdir(parents=True, exist_ok=True)

    def _resolve_file(self, value):
        if not value:
            return None

        path = Path(value)
        if path.is_absolute():
            return path

        # Prefer a path already valid from the current working directory.
        if path.exists():
            return path

        # Normal asset references such as assets/video/scene_001/...
        candidate = self.project_path / path
        if candidate.exists():
            return candidate

        # Stored project-relative paths such as
        # projects/test_movie/assets/video/scene_001/...
        project_prefix = str(self.project_path).rstrip("/") + "/"
        value_str = str(value)
        if value_str.startswith(project_prefix):
            candidate = Path(value_str)
            if candidate.exists():
                return candidate

        return candidate

    def collect_render_results(self):
        results = []
        if not self.render_path.exists():
            return results

        for file in sorted(self.render_path.rglob("render_result.json")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            data["_render_result_file"] = str(file)
            results.append(data)

        return results

    def collect_video_assets(self, renders=None):
        """Collect assets referenced by render results, never stale shot manifests."""
        if renders is None:
            renders = self.collect_render_results()

        assets = []
        seen = set()

        for render in renders:
            render_scene_id = render.get("scene_id")
            for task in render.get("tasks", []):
                if task.get("type") != "video":
                    continue

                result = task.get("result") or {}
                asset_file = result.get("asset_file")
                asset_id = result.get("asset_id") or task.get("task_id")

                if not asset_file or not asset_id or asset_id in seen:
                    continue

                resolved = self._resolve_file(asset_file)
                if resolved is None or not resolved.is_file():
                    continue

                metadata = dict(result.get("metadata") or {})
                task_metadata = dict(task.get("metadata") or {})

                scene_id = metadata.get("scene_id", task_metadata.get("scene_id", render_scene_id))
                shot_id = metadata.get("shot_id", task_metadata.get("shot_id"))
                timeline = metadata.get("timeline") or task_metadata.get("timeline") or {}

                asset = dict(result)
                asset["asset_file"] = str(asset_file)
                asset["resolved_asset_file"] = str(resolved)
                asset["metadata"] = metadata
                asset["scene_id"] = scene_id
                asset["shot_id"] = shot_id
                asset["timeline"] = timeline
                asset["source_task_id"] = task.get("task_id")
                asset["source_render_result"] = render.get("_render_result_file")

                assets.append(asset)
                seen.add(asset_id)

        return assets

    def sort_assets_by_timeline(self, assets):
        return sorted(
            assets,
            key=lambda asset: (
                asset.get("scene_id", 0),
                (asset.get("timeline") or {}).get("start", 0),
                asset.get("shot_id", 0),
            ),
        )

    def _build_timeline(self, assets):
        timeline = []
        for asset in assets:
            timeline_data = asset.get("timeline") or {}
            timeline.append(
                {
                    "scene_id": asset.get("scene_id"),
                    "shot_id": asset.get("shot_id"),
                    "start": timeline_data.get("start", 0),
                    "duration": timeline_data.get("duration", 0),
                    "asset_id": asset.get("asset_id"),
                    "asset_file": asset.get("asset_file"),
                }
            )
        return timeline

    def compile_movie(self):
        renders = self.collect_render_results()
        assets = self.sort_assets_by_timeline(self.collect_video_assets(renders))

        validation_errors = []
        for render in renders:
            expected = render.get("shot_count")
            rendered = render.get("rendered")
            if expected is not None and rendered != expected:
                validation_errors.append(
                    f"Scene {render.get('scene_id')} render count mismatch: expected {expected}, got {rendered}"
                )
            expected_ids = [int(x) for x in render.get("shot_ids", [])]
            actual_ids = sorted(
                int(a["shot_id"]) for a in assets
                if a.get("scene_id") == render.get("scene_id") and a.get("shot_id") is not None
            )
            if expected_ids and actual_ids != sorted(expected_ids):
                validation_errors.append(
                    f"Scene {render.get('scene_id')} asset shots mismatch: expected {sorted(expected_ids)}, got {actual_ids}"
                )

        movie = {
            "created": datetime.now().isoformat(),
            "project": str(self.project_path),
            "quality": "Master 8K",
            "timeline": self._build_timeline(assets),
            "assets_count": len(assets),
            "render_count": len(renders),
            "assets": assets,
            "renders": renders,
            "validation": {
                "status": "ready" if not validation_errors else "failed",
                "errors": validation_errors,
            },
            "status": "compiled" if not validation_errors else "compiled_with_errors",
        }
        if validation_errors:
            raise RuntimeError("Movie compilation validation failed: " + "; ".join(validation_errors))

        output = self.final_path / "master_movie.json"
        output.write_text(
            json.dumps(movie, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(output)

    def load_movie(self):
        file = self.final_path / "master_movie.json"
        if not file.exists():
            return None
        return json.loads(file.read_text(encoding="utf-8"))
