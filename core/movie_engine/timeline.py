from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class TimelineItem:

    scene_id: int

    start: float

    duration: float

    media: Dict[str, Any] = field(
        default_factory=dict
    )



class Timeline:


    def __init__(self):

        self.items: List[TimelineItem] = []



    def add_scene(
        self,
        scene_id: int,
        duration: float,
        media: Dict[str, Any]
    ):

        item = TimelineItem(

            scene_id=scene_id,

            start=self.total_duration(),

            duration=float(duration),

            media=media

        )


        self.items.append(item)


        return item



    def remove_scene(
        self,
        scene_id: int
    ):

        self.items = [

            item

            for item in self.items

            if item.scene_id != scene_id

        ]

        self.rebuild()



    def rebuild(self):

        current_time = 0


        for item in self.items:

            item.start = current_time

            current_time += item.duration



    def get_scene(
        self,
        scene_id: int
    ):

        for item in self.items:

            if item.scene_id == scene_id:

                return item

        return None



    def get_timeline(self):

        return [

            {

                "scene_id": item.scene_id,

                "start": item.start,

                "duration": item.duration,

                "media": item.media

            }

            for item in self.items

        ]



    def total_duration(self):

        return sum(

            item.duration

            for item in self.items

        )



    def clear(self):

        self.items.clear()
