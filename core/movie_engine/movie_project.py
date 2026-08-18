from pathlib import Path
import json
from datetime import datetime

from core.movie_engine.movie_pipeline import MoviePipeline
from core.movie_engine.quality_manager import QualityManager
from core.movie_engine.timeline import Timeline
from core.movie_engine.scene_manager import SceneManager
from core.movie_engine.storyboard_engine import StoryboardEngine


class MovieProject:
    """
    Movie project facade.

    4K is the automatic default. An explicit 8K selection is preserved and
    passed through to the provider-capability resolver.
    """

    def __init__(self, project_path="projects/test_movie", quality="4k"):
        self.project_path = Path(project_path)
        self.project_path.mkdir(parents=True, exist_ok=True)

        self.pipeline = MoviePipeline(self.project_path)
        self.quality_manager = QualityManager(quality)
        self.timeline = Timeline()
        self.scene_manager = SceneManager(self.project_path)
        self.storyboard = StoryboardEngine(self.project_path)
        self.scenes = []

    def add_scene(self, scene_id, scene_data, duration):
        result = self.pipeline.create_scene(scene_id, scene_data, duration)
        media = result["timeline"][-1]["media"]

        scene = {
            "scene_id": scene_id,
            "duration": float(duration),
            "created": datetime.now().isoformat(),
            "media": media,
        }

        self.scenes.append(scene)
        self.timeline.add_scene(scene_id, float(duration), media)
        self.scene_manager.create_scene(scene_id, media, duration)
        self.storyboard.create_storyboard(scene_id, scene_data, duration)

        return scene

    def get_movie(self):
        return {
            "quality": self.quality_manager.get_settings(),
            "audio": {
                "quality": "stereo",
                "channels": 2,
                "channel_layout": "stereo",
            },
            "scenes": [
                {
                    "scene_id": scene["scene_id"],
                    "duration": scene["duration"],
                    "created": scene["created"],
                }
                for scene in self.scenes
            ],
            "timeline": self.timeline.get_timeline(),
            "total_duration": self.timeline.total_duration(),
        }

    def save(self):
        file = self.project_path / "movie_project.json"
        file.write_text(
            json.dumps(self.get_movie(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(file)
