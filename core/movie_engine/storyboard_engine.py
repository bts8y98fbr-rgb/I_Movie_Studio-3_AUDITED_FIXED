from pathlib import Path
import json
from datetime import datetime


class StoryboardEngine:

    def __init__(self, project_path):

        self.project_path = Path(project_path)

        self.storyboard_path = (
            self.project_path /
            "storyboard"
        )

        self.director_path = (
            self.project_path /
            "director"
        )

        self.storyboard_path.mkdir(
            parents=True,
            exist_ok=True
        )

        self.director_path.mkdir(
            parents=True,
            exist_ok=True
        )


    def create_storyboard(
        self,
        scene_id,
        scene_data,
        duration
    ):

        scene_folder = (
            self.storyboard_path /
            f"scene_{scene_id:03d}"
        )

        scene_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        visual = scene_data.get(
            "visual",
            ""
        )

        video = scene_data.get(
            "video",
            ""
        )

        shots = self._create_shots(
            visual,
            video,
            float(duration)
        )

        storyboard = {

            "scene_id":
                scene_id,

            "created":
                datetime.now().isoformat(),

            "source":
                "Storyboard Engine",

            "duration":
                float(duration),

            "shot_count":
                len(shots),

            "shots":
                shots
        }


        file = (
            scene_folder /
            "storyboard.json"
        )


        file.write_text(
            json.dumps(
                storyboard,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )


        return file



    def create_from_director(
        self,
        scene_id
    ):

        director_file = (
            self.director_path /
            f"scene_{scene_id:03d}_director.json"
        )


        if not director_file.exists():

            raise FileNotFoundError(
                f"Director file not found: {director_file}"
            )


        director_data = json.loads(

            director_file.read_text(
                encoding="utf-8"
            )

        )


        storyboard = {

            "scene_id":
                scene_id,

            "created":
                datetime.now().isoformat(),

            "source":
                "AI Director",

            "scene_type":
                director_data.get(
                    "scene_type",
                    "unknown"
                ),

            "quality":
                director_data.get(
                    "quality",
                    "8k"
                ),

            "duration":
                director_data.get(
                    "duration",
                    0
                ),

            "shot_count":
                len(
                    director_data.get(
                        "shots",
                        []
                    )
                ),

            "shots":
                director_data.get(
                    "shots",
                    []
                )

        }


        scene_folder = (

            self.storyboard_path /
            f"scene_{scene_id:03d}"

        )


        scene_folder.mkdir(
            parents=True,
            exist_ok=True
        )


        file = (

            scene_folder /
            "storyboard.json"

        )


        file.write_text(

            json.dumps(
                storyboard,
                indent=2,
                ensure_ascii=False
            ),

            encoding="utf-8"

        )


        return file



    def _create_shots(
        self,
        visual,
        video,
        duration
    ):

        shots = []


        if duration <= 5:

            segments = [
                duration
            ]

        elif duration <= 10:

            segments = [
                3,
                duration - 3
            ]

        else:

            segments = [
                3,
                4,
                duration - 7
            ]


        shot_types = [

            (
                "wide_establishing",
                "slow_tracking"
            ),

            (
                "medium_action",
                "camera_move"
            ),

            (
                "close_detail",
                "slow_push_in"
            )

        ]


        start = 0


        for index, length in enumerate(
            segments,
            start=1
        ):


            camera_type, movement = (
                shot_types[
                    min(
                        index - 1,
                        len(shot_types)-1
                    )
                ]
            )


            shot = {

                "shot_id":
                    index,

                "start":
                    start,

                "duration":
                    float(length),

                "camera":
                {

                    "type":
                        "cinematic",

                    "shot_type":
                        camera_type,

                    "movement":
                        movement
                },


                "lens":
                {

                    "type":
                        "anamorphic",

                    "focal_length":
                        "35mm"
                },


                "lighting":
                {

                    "style":
                        "cinematic",

                    "source":
                        "volumetric"
                },


                "atmosphere":
                {

                    "environment":
                        visual,

                    "mood":
                        "epic"
                },


                "vfx":
                [
                    "depth_of_field",
                    "cinematic_particles"
                ],


                "color_grade":
                {

                    "profile":
                        "HDR cinematic",

                    "contrast":
                        "high"
                },


                "ai_prompt":
                    (
                        f"8K HDR cinematic shot, "
                        f"{visual}, "
                        f"{video}, "
                        f"{camera_type}, "
                        f"{movement}, "
                        "anamorphic lens, "
                        "volumetric lighting"
                    )

            }


            shots.append(
                shot
            )


            start += length


        return shots



    def load_storyboard(
        self,
        scene_id
    ):

        file = (

            self.storyboard_path /
            f"scene_{scene_id:03d}" /
            "storyboard.json"

        )


        return json.loads(

            file.read_text(
                encoding="utf-8"
            )

        )
