from pathlib import Path

from core.ai_core.ai_director import AIDirector

from core.ai_core.generation_queue import (
    GenerationQueue,
    GenerationTask,
)

from core.ai_core.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)

from core.ai_core.providers.video.video_provider import (
    VideoProvider,
)

from core.movie_engine.scene_builder import SceneBuilder


class MoviePipeline:
    """
    Coordinates AI movie production.

    Flow:

    AI Director
        ->
    Production Orchestrator
        ->
    Generation Queue
        ->
    Video Provider
        ->
    Scene Builder
        ->
    Timeline


    Backward compatible:

        MoviePipeline(project_path)
    """

    def __init__(
        self,
        project_path="projects/test_movie",
        ai_director=None,
        scene_builder=None,
        generation_queue=None,
        video_provider=None,
        production_orchestrator=None,
    ):

        self.project_path = Path(
            project_path
        )

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

        self.generation_queue = (
            generation_queue
            or GenerationQueue()
        )

        self.video_provider = (
            video_provider
            or VideoProvider()
        )

        self.production_orchestrator = (
            production_orchestrator
            or ProductionOrchestrator()
        )


    def create_scene(
        self,
        scene_id,
        scene_data,
        duration=5,
    ):

        production_plan = (
            self.production_orchestrator
            .plan_scene(
                scene_id,
                "high"
            )
        )

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

            "production_plan":
                production_plan,

            "director_file":
                director_file,

            "direction":
                direction,

            "generated_tasks":
                [
                    {
                        "task_id":
                            task.task_id,

                        "status":
                            task.status,

                        "result":
                            task.result,
                    }

                    for task in generated_tasks
                ],

            "timeline":
                self.scene_builder
                .get_movie_timeline(),

            "scene":
                timeline_item,
        }

    def regenerate_from_master_prompt(
        self,
        prompt,
        affected_scene_ids=None,
    ):
        scene_ids = (
            list(self._scene_inputs)
            if affected_scene_ids is None
            else list(affected_scene_ids)
        )
        return self.reactive_orchestrator.apply(prompt, scene_ids)

    def _regenerate_scene_from_master_prompt(
        self,
        scene_id,
        prompt,
    ):
        original = self._scene_inputs.get(int(scene_id))
        if original is None:
            return {
                "status": "skipped",
                "scene_id": scene_id,
                "reason": "Scene is not registered in this pipeline",
            }

        scene_data = dict(original["scene_data"])
        scene_data["master_prompt"] = prompt
        result = self.create_scene(
            scene_id,
            scene_data,
            original["duration"],
        )
        return {
            "status": "submitted",
            "scene_id": scene_id,
            "generated_tasks": len(result.get("generated_tasks", [])),
        }


    def _queue_shots(
        self,
        scene_id,
        direction,
        duration,
    ):

        for shot in direction.get(
            "shots",
            [],
        ):

            task = GenerationTask(

                task_type=
                    f"shot_{shot.get('shot_id', 0)}",

                prompt=
                    shot.get(
                        "director_prompt",
                        "",
                    ),

                provider=
                    self.video_provider,

                quality=None,

                project_path=
                    self.project_path,

                metadata={

                    "scene_id":
                        scene_id,

                    "shot_id":
                        shot.get(
                            "shot_id",
                            0,
                        ),

                    "duration":
                        shot.get(
                            "duration",
                            duration,
                        ),

                    "camera":
                        shot.get(
                            "camera",
                            {},
                        ),

                    "scene_type":
                        shot.get(
                            "scene_type",
                            "cinematic",
                        ),
                },
            )


            self.generation_queue.add_task(
                task
            )


    @staticmethod
    def _task_to_asset(task):

        class GeneratedAsset:
            pass


        class Provider:
            pass


        asset = GeneratedAsset()

        provider = Provider()

        provider.name = (
            task.provider.name
        )

        asset.task_type = (
            task.task_type
        )

        asset.provider = provider

        asset.result = (
            task.result
        )

        return asset
