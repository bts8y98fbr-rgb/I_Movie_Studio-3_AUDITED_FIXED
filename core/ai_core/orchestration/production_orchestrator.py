from core.ai_core.orchestration.resource_manager import (
    ResourceManager,
)


class ProductionOrchestrator:
    """
    Main production coordinator.

    Does not generate media locally.

    Coordinates:
        AI Director
        Resource Manager
        Provider Pool
        Generation Queue
    """


    def __init__(
        self,
        resource_manager=None,
        provider_pool=None,
        generation_queue=None,
    ):

        self.resource_manager = (
            resource_manager
            or ResourceManager()
        )

        self.provider_pool = (
            provider_pool
        )

        self.generation_queue = (
            generation_queue
        )


    def plan_scene(
        self,
        scene_id,
        complexity="normal",
    ):

        allocations = (
            self.resource_manager
            .plan_video_scene(
                complexity
            )
        )

        return {

            "scene_id": scene_id,

            "status": "planned",

            "workers":
                sum(
                    item.workers
                    for item in allocations
                ),

            "allocations":
                [
                    {
                        "type":
                            item.media_type,

                        "workers":
                            item.workers,

                        "quality":
                            item.quality,

                    }

                    for item in allocations
                ],

        }


    def execute_scene(
        self,
        scene_id,
        complexity="normal",
    ):

        plan = self.plan_scene(
            scene_id,
            complexity,
        )

        plan["status"] = (
            "scheduled"
        )

        return plan
