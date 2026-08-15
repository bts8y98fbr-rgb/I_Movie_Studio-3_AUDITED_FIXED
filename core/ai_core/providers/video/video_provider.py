from datetime import datetime
import json
from pathlib import Path
import uuid

from core.ai_core.providers.base_provider import BaseAIProvider


class VideoProvider(BaseAIProvider):
    """Deterministic video-generation adapter.

    The current implementation creates a generation manifest rather than a
    real video file. The provider contract is kept compatible with a future
    external video API.
    """

    def __init__(self, name="Video AI"):
        super().__init__(name)

    def generate(self, prompt, **kwargs):
        project_path = Path(kwargs.get("project_path") or "projects/test_movie")
        metadata = dict(kwargs.get("metadata") or {})

        if "scene_id" not in metadata or "shot_id" not in metadata:
            raise ValueError("Video generation requires scene_id and shot_id metadata")

        try:
            scene_id = int(metadata["scene_id"])
            shot_id = int(metadata["shot_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("scene_id and shot_id must be integers") from exc

        if scene_id < 0 or shot_id < 0:
            raise ValueError("scene_id and shot_id must be non-negative")

        quality_settings = metadata.get("quality")
        if not isinstance(quality_settings, dict):
            quality_settings = {}

        asset_id = str(uuid.uuid4())[:8]
        asset_path = (
            project_path
            / "assets"
            / "video"
            / f"scene_{scene_id:03d}"
            / f"shot_{shot_id:03d}"
        )
        asset_path.mkdir(parents=True, exist_ok=True)

        asset_file = asset_path / f"{asset_id}.json"

        result = {
            "asset_id": asset_id,
            "type": "video",
            "provider": self.name,
            "prompt": prompt,
            "status": "generated",
            "asset_path": str(asset_path),
            "asset_file": str(asset_file),
            "created": datetime.now().isoformat(),
            "metadata": {
                "scene_id": scene_id,
                "shot_id": shot_id,
                "duration": metadata.get("duration"),
                "fps": quality_settings.get("fps", 60),
                "resolution": quality_settings.get("resolution", "7680x4320"),
                "hdr": quality_settings.get("hdr", True),
                "color_depth": quality_settings.get("color_depth", 10),
                "timeline": metadata.get("timeline", {}),
                "camera": metadata.get("camera", {}),
            },
        }

        asset_file.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return result
