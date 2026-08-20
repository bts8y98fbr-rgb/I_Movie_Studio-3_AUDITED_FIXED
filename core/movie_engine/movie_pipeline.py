from pathlib import Path

from core.ai_core.ai_director import AIDirector

from core.ai_core.generation_queue import (
    GenerationQueue,
    GenerationTask,
)

from core.ai_core.providers.video import (
    VideoRouter,
    RemoteVideoProvider,
)

from core.movie_engine.scene_builder import SceneBuilder


class MoviePipeline:
    """
    Coordinates AI direction, remote video generation
    and timeline creation.

    Flow:

    AI Director
        ->
    Generation Queue
        ->
    Video Router
        ->
    Remote Video Provider
        ->
    Scene Builder
        ->
    Timeline
    """

    def __init__(
        self,
        project_path="projects/test_movie",
        ai_director=None,
        scene_builder=None,
        generation_queue=None,
        video_provider=None,
    ):

        self.project_path = Path(project_path)

        self.ai_director = (
            ai_director
            or AIDirector(self.project_path)
        )

        self.scene_builder = (
            scene_builder
            or SceneBuilder()
        )

        self.generation_queue = (
            generation_queue
            or GenerationQueue()
        )

        if video_provider:
            self.video_router = video_provider
        else:
            self.video_router = VideoRouter(
                [
                    RemoteVideoProvider()
                ]
            )

        self.video_provider = (
            self.video_router.select()
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
                f"No AI direction for scene {scene_id}"
            )

        self._queue_shots(
            scene_id,
            direction,
            duration,
        )

        generated_tasks = (
            self.generation_queue.process_all()
        )

        generated_assets = []

        for task in generated_tasks:
            if task.status != "done":
                continue

            generated_assets.append(
                self._task_to_asset(task)
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
            "generated_tasks": [
                {
                    "task_id": task.task_id,
                    "status": task.status,
                    "result": task.result,
                }
                for task in generated_tasks
            ],
            "timeline": (
                self.scene_builder.get_movie_timeline()
            ),
            "scene": timeline_item,
        }


    def _queue_shots(
        self,
        scene_id,
        direction,
        duration,
    ):

        for shot in direction.get("shots", []):

            task = GenerationTask(
                task_type=(
                    f"shot_{shot.get('shot_id', 0)}"
                ),

                prompt=shot.get(
                    "director_prompt",
                    "",
                ),

                provider=self.video_provider,

                quality="8k",

                project_path=self.project_path,

                metadata={
                    "scene_id": scene_id,

                    "shot_id": shot.get(
                        "shot_id",
                        0,
                    ),

                    "duration": shot.get(
                        "duration",
                        duration,
                    ),

                    "camera": shot.get(
                        "camera",
                        {},
                    ),
                },
            )

            self.generation_queue.add_task(task)


    @staticmethod
    def _task_to_asset(task):

        class GeneratedAsset:
            pass

        class Provider:
            pass

        asset = GeneratedAsset()

        provider = Provider()

        provider.name = task.provider.name

        asset.task_type = task.task_type

        asset.provider = provider

        asset.result = task.result

        return asset
