from pathlib import Path
import json

from core.movie_engine.render_preset_manager import RenderPresetManager
from core.movie_engine.generation_engine import GenerationEngine
from render.render_pipeline import RenderPipeline


class RenderEngine:
    def __init__(self, project_path="projects/test_movie", quality="4k"):
        self.project_path = Path(project_path)
        self.quality = quality
        self.render_path = self.project_path / "render_output"
        self.render_path.mkdir(parents=True, exist_ok=True)

        self.preset = RenderPresetManager(quality)
        self.generation_engine = GenerationEngine(
            project_path,
            quality,
        )

    def render_scene(self, scene_id):
        render_plan_path = (
            self.project_path / "render"
            / f"scene_{scene_id:03d}"
            / "render_plan.json"
        )
        if not render_plan_path.exists():
            raise FileNotFoundError(
                f"Render plan not found: {render_plan_path}"
            )

        generation_file = self.generation_engine.generate_scene(scene_id)

        with open(generation_file, "r", encoding="utf-8") as file:
            json.load(file)

        return RenderPipeline(self.project_path).render_plan(render_plan_path)

    def load_render_result(self, scene_id):
        result_file = (
            self.render_path / f"scene_{scene_id:03d}"
            / "render_result.json"
        )
        with open(result_file, "r", encoding="utf-8") as file:
            return json.load(file)
