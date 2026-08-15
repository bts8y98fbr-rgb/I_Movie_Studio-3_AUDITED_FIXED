from datetime import datetime
import json
from pathlib import Path


class ExportPipeline:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.exports_path = self.project_path / "exports"
        self.plan_path = self.exports_path / "export_plan.json"
        self.output_path = self.exports_path / "movie_export.json"

    def load_export_plan(self):
        if not self.plan_path.exists():
            raise FileNotFoundError("export_plan.json not found")
        return json.loads(self.plan_path.read_text(encoding="utf-8"))

    def _resolve_file(self, value):
        if not value:
            return None
        path = Path(value)
        if path.is_absolute():
            return path
        if path.exists():
            return path
        return self.project_path / path

    def validate_timeline(self, timeline):
        errors = []
        last_end = 0
        for item in sorted(timeline, key=lambda x: (x.get("start", 0), x.get("shot_id", 0))):
            start = item.get("start", 0)
            duration = item.get("duration", 0)
            if duration <= 0:
                errors.append(f"Invalid duration at shot {item.get('shot_id')}")
            if start < last_end:
                errors.append(f"Timeline overlap at shot {item.get('shot_id')}")
            last_end = max(last_end, start + duration)
        return errors

    def build_video_tracks(self, assets):
        tracks = []
        for asset in assets:
            if asset.get("type") != "video":
                continue

            asset_file = asset.get("asset_file")
            resolved = self._resolve_file(asset_file)
            tracks.append(
                {
                    "asset_id": asset.get("asset_id"),
                    "file": asset_file,
                    "resolved_file": str(resolved) if resolved else None,
                    "file_exists": bool(resolved and resolved.is_file()),
                    "scene_id": asset.get("scene_id", (asset.get("metadata") or {}).get("scene_id")),
                    "shot_id": asset.get("shot_id", (asset.get("metadata") or {}).get("shot_id")),
                }
            )
        return tracks

    def build_audio_tracks(self):
        return [{"type": "audio", "status": "empty", "tracks": []}]

    def create_export_package(self):
        plan = self.load_export_plan()
        timeline_errors = self.validate_timeline(plan.get("timeline", []))
        video_tracks = self.build_video_tracks(plan.get("assets", []))

        missing_files = [
            track["asset_id"]
            for track in video_tracks
            if not track["file_exists"]
        ]
        if missing_files:
            timeline_errors.extend(
                f"Video asset file not found: {asset_id}"
                for asset_id in missing_files
            )

        if plan.get("validation", {}).get("status") == "failed":
            timeline_errors.extend(plan.get("validation", {}).get("errors", []))

        package = {
            "created": datetime.now().isoformat(),
            "project": str(self.project_path),
            "quality": plan.get("quality"),
            "timeline": plan.get("timeline", []),
            "video_tracks": video_tracks,
            "audio_tracks": self.build_audio_tracks(),
            "render_data": plan.get("renders", []),
            "validation": {
                "status": "ready" if not timeline_errors else "failed",
                "errors": timeline_errors,
            },
            "export_settings": plan.get("export", {}),
        }

        self.output_path.write_text(
            json.dumps(package, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(self.output_path)

    def load_export_package(self):
        if not self.output_path.exists():
            raise FileNotFoundError("movie_export.json not found")
        return json.loads(self.output_path.read_text(encoding="utf-8"))
