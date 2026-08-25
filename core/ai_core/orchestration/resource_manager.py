from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ResourceAllocation:
    media_type: str
    workers: int
    priority: int
    quality: str


class ResourceManager:
    """
    Dynamic resource scheduler for AI providers.

    Controls distribution between:
        - video
        - image
        - voice
        - music

    Heavy generation runs remotely.
    Local machine only schedules jobs.
    """

    def __init__(
        self,
        min_workers=10,
        max_workers=100,
    ):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.allocations: List[
            ResourceAllocation
        ] = []


    def allocate(
        self,
        requirements: Dict[str, int],
        quality="adaptive",
    ):

        self.allocations.clear()

        total = sum(
            requirements.values()
        )

        for media_type, priority in requirements.items():

            workers = max(
                1,
                int(
                    self.max_workers
                    *
                    priority
                    /
                    total
                )
            )

            self.allocations.append(
                ResourceAllocation(
                    media_type=media_type,
                    workers=workers,
                    priority=priority,
                    quality=quality,
                )
            )

        self._ensure_minimum()

        return self.allocations


    def _ensure_minimum(self):

        current = sum(
            item.workers
            for item in self.allocations
        )

        if current < self.min_workers:

            self.allocations[0].workers += (
                self.min_workers - current
            )


    def plan_video_scene(
        self,
        complexity="normal",
    ):

        if complexity == "high":

            return self.allocate(
                {
                    "video": 70,
                    "voice": 20,
                    "music": 10,
                },
                quality="maximum",
            )


        return self.allocate(
            {
                "video": 80,
                "voice": 15,
                "music": 5,
            }
        )


    def status(self):

        return {
            "min_workers": self.min_workers,
            "max_workers": self.max_workers,
            "allocations": [
                {
                    "type": item.media_type,
                    "workers": item.workers,
                    "priority": item.priority,
                    "quality": item.quality,
                }
                for item in self.allocations
            ],
        }
