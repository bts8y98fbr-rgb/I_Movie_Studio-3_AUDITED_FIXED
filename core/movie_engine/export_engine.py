from datetime import datetime
import json
from pathlib import Path


class ExportEngine:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.final_path = self.project_path / "final" / "master_movie.json"
        self.export_path = self.project_path / "exports"
        self.export_path.mkdir(parents=True, exist_ok=True)

    def load_master_movie(self):
        if not self.final_path.exists():
            raise FileNotFoundError("master_movie.json not found")
        return json.loads(self.final_path.read_text(encoding="utf-8"))

    def _resolve_file(self, value):
        if not value:
            return None
        path = Path(value)
        if path.is_absolute():
            return path
        if path.exists():
            return path
        candidate = self.project_path / path
        if candidate.exists():
            return candidate
        return candidate

    def validate_movie(self, movie):
        errors = []

        assets = movie.get("assets", [])
        renders = movie.get("renders", [])

        if not assets:
            errors.append("No assets found")
        if not renders:
            errors.append("No render data found")

        seen_asset_ids = set()
        for asset in assets:
            asset_id = asset.get("asset_id")
            asset_file = asset.get("asset_file")

            if not asset_id:
                errors.append("Asset missing asset_id")
            elif asset_id in seen_asset_ids:
                errors.append(f"Duplicate asset {asset_id}")
            else:
                seen_asset_ids.add(asset_id)

            if not asset_file:
                errors.append(f"Asset {asset_id} missing file")
            elif not self._resolve_file(asset_file).is_file():
                errors.append(f"Asset {asset_id} file not found: {asset_file}")

        timeline = sorted(
            movie.get("timeline", []),
            key=lambda item: (item.get("start", 0), item.get("shot_id", 0)),
        )
        last_end = 0
        for item in timeline:
            start = item.get("start", 0)
            duration = item.get("duration", 0)
            if duration <= 0:
                errors.append(f"Invalid duration at shot {item.get('shot_id')}")
            if start < last_end:
                errors.append(f"Timeline overlap at shot {item.get('shot_id')}")
            last_end = max(last_end, start + duration)

        if len(timeline) != len(assets):
            errors.append(
                f"Timeline/assets count mismatch: {len(timeline)} timeline items, {len(assets)} assets"
            )

        return errors

    def create_export_plan(self):
        movie = self.load_master_movie()
        errors = self.validate_movie(movie)

        export_plan = {
            "created": datetime.now().isoformat(),
            "project": str(self.project_path),
            "quality": movie.get("quality"),
            "timeline": movie.get("timeline", []),
            "assets": movie.get("assets", []),
            "renders": movie.get("renders", []),
            "validation": {
                "status": "ready" if not errors else "failed",
                "errors": errors,
            },
            "export": {
                "format": "mp4",
                "codec": "h265",
                "resolution": "7680x4320",
                "fps": 60,
                "hdr": True,
            },
        }

        output = self.export_path / "export_plan.json"
        output.write_text(
            json.dumps(export_plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(output)

    def load_export_plan(self):
        path = self.export_path / "export_plan.json"
        if not path.exists():
            raise FileNotFoundError("export_plan.json not found")
        return json.loads(path.read_text(encoding="utf-8"))
