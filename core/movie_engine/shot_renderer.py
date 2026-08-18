from pathlib import Path
import json
from datetime import datetime

from core.movie_engine.render_preset_manager import RenderPresetManager
from core.ai_core.quality_policy import QualityPolicy
from core.ai_core.model_router import ModelRouter
from core.ai_core.shot_model_selector import ShotModelSelector


class ShotRenderer:
    def __init__(self, project_path, quality="4k"):
        self.project_path = Path(project_path)
        self.quality = quality
        self.storyboard_path = self.project_path / "storyboard"
        self.render_path = self.project_path / "render"
        self.render_path.mkdir(parents=True, exist_ok=True)

        self.preset = RenderPresetManager(quality)
        self.quality_policy = QualityPolicy(quality)
        self.model_router = ModelRouter(self.quality_policy)
        self.shot_selector = ShotModelSelector(self.model_router)

    def create_render_plan(self, scene_id):
        storyboard_file = (
            self.storyboard_path / f"scene_{scene_id:03d}" / "storyboard.json"
        )
        if not storyboard_file.exists():
            raise FileNotFoundError(storyboard_file)

        storyboard = json.loads(
            storyboard_file.read_text(encoding="utf-8")
        )

        shots = []
        for shot in storyboard.get("shots", []):
            shot_model = self.shot_selector.select_for_shot(shot)

            shots.append({
                "scene_id": scene_id,
                "shot_id": shot["shot_id"],
                "timeline": {
                    "start": shot.get("start", 0),
                    "duration": shot.get("duration", 0),
                },
                "camera": shot.get("camera", {}),
                "director_prompt": shot.get(
                    "director_prompt",
                    shot.get("ai_prompt", ""),
                ),
                "quality": self.preset.get_settings(),
                "shot_model_selection": shot_model,
            })

        render_plan = {
            "scene_id": scene_id,
            "created": datetime.now().isoformat(),
            "quality": self.quality,
            "render_settings": self.preset.get_settings(),
            "audio": self.quality_policy.get_audio_defaults(),
            "source": "AI Director Storyboard",
            "shot_selection": "AI Shot Model Selector",
            "shot_count": len(shots),
            "shots": shots,
        }

        scene_folder = self.render_path / f"scene_{scene_id:03d}"
        scene_folder.mkdir(parents=True, exist_ok=True)

        file = scene_folder / "render_plan.json"
        file.write_text(
            json.dumps(render_plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return file

    def load_render_plan(self, scene_id):
        file = (
            self.render_path
            / f"scene_{scene_id:03d}"
            / "render_plan.json"
        )
        return json.loads(file.read_text(encoding="utf-8"))
