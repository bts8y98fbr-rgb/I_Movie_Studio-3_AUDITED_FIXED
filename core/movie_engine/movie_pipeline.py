from pathlib import Path

from core.ai_core.ai_director import AIDirector
from core.movie_engine.scene_builder import SceneBuilder


class MoviePipeline:
    """
    Coordinates AI direction and scene construction.

    AIDirector is responsible for creating the cinematic direction.
    SceneBuilder is responsible for converting the resulting direction
    into the movie timeline representation.
    """

    def __init__(
        self,
        project_path="projects/test_movie",
        ai_director=None,
        scene_builder=None,
    ):
        self.project_path = Path(project_path)

        self.ai_director = (
            ai_director
            or AIDirector(
                self.project_path
            )
        )

        self.scene_builder = (
            scene_builder
            or SceneBuilder()
        )

    def create_scene(
        self,
        scene_id,
        scene_data,
        duration=5,
    ):
        director_file = (
            self.ai_director.analyze_scene(
                scene_id,
                scene_data,
                duration,
            )
        )

        direction = (
            self.ai_director.load_direction(
                scene_id
            )
        )

        if direction is None:
            raise RuntimeError(
                "AI Director produced no direction "
                f"for scene {scene_id}: {director_file}"
            )

        generated_assets = []

        for shot in direction.get(
            "shots",
            [],
        ):
            generated_assets.append(
                self._build_direction_asset(
                    scene_id,
                    shot,
                )
            )

        timeline_item = (
            self.scene_builder.build_scene(
                scene_id,
                duration,
                generated_assets,
            )
        )

        return {
            "scene_id": scene_id,
            "duration": float(duration),
            "director_file": director_file,
            "direction": direction,
            "timeline": (
                self.scene_builder
                .get_movie_timeline()
            ),
            "scene": timeline_item,
        }

    @staticmethod
    def _build_direction_asset(
        scene_id,
        shot,
    ):
        """
        Convert a director shot into the minimal asset contract
        expected by SceneBuilder.

        This is intentionally an internal adapter. The real media
        generation providers will be connected later.
        """

        class DirectionAsset:
            pass

        class DirectionProvider:
            name = "ai_director"

        asset = DirectionAsset()

        asset.task_type = (
            f"shot_{shot.get('shot_id', 0)}"
        )

        asset.provider = DirectionProvider()

        asset.result = {
            "scene_id": scene_id,
            "shot_id": shot.get(
                "shot_id"
            ),
            "start": shot.get(
                "start",
                0,
            ),
            "duration": shot.get(
                "duration",
                0,
            ),
            "camera": shot.get(
                "camera",
                {},
            ),
            "scene_type": shot.get(
                "scene_type",
                "cinematic",
            ),
            "director_prompt": shot.get(
                "director_prompt",
                "",
            ),
        }

        return asset
