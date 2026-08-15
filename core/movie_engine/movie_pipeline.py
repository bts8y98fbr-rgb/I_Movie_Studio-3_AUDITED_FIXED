from core.ai_core.ai_director import AIDirector
from core.movie_engine.scene_builder import SceneBuilder
from pathlib import Path


class MoviePipeline:

    def __init__(self, project_path="projects/test_movie"):

        self.project_path = Path(project_path)

        self.ai_director = AIDirector(
            self.project_path
        )

        self.scene_builder = SceneBuilder()


    def create_scene(
        self,
        scene_id,
        scene_data,
        duration=5
    ):

        self.ai_director.analyze_scene(
            scene_data
        )

        tasks = self.ai_director.process_scene()


        self.scene_builder.build_scene(
            scene_id,
            duration,
            tasks
        )


        return {
            "scene_id": scene_id,
            "duration": duration,
            "timeline": self.scene_builder.get_movie_timeline()
        }
