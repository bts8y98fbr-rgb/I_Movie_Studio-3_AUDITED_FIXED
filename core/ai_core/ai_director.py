from datetime import datetime
from pathlib import Path
import json


class AIDirector:

    def __init__(
        self,
        project_path="projects/test_movie",
        quality="8k"
    ):

        self.project_path = Path(project_path)
        self.quality = quality

        self.director_path = (
            self.project_path /
            "director"
        )

        self.director_path.mkdir(
            parents=True,
            exist_ok=True
        )


    def detect_scene_type(
        self,
        scene_data
    ):

        text = (
            str(scene_data)
            .lower()
        )

        if any(
            x in text
            for x in [
                "battle",
                "fight",
                "attack",
                "war"
            ]
        ):
            return "action"


        if any(
            x in text
            for x in [
                "space",
                "station",
                "planet",
                "galaxy"
            ]
        ):
            return "epic_space"


        if any(
            x in text
            for x in [
                "dark",
                "horror",
                "fear"
            ]
        ):
            return "horror"


        if any(
            x in text
            for x in [
                "talk",
                "dialogue",
                "conversation"
            ]
        ):
            return "dialogue"


        return "cinematic"


    def build_shot(
        self,
        shot_id,
        start,
        duration,
        visual,
        action,
        scene_type
    ):

        if scene_type == "action":

            shots = [
                (
                    "dynamic_wide",
                    "fast_tracking"
                ),
                (
                    "close_action",
                    "handheld_motion"
                )
            ]


        elif scene_type == "epic_space":

            shots = [
                (
                    "wide_establishing",
                    "slow_orbit"
                ),
                (
                    "hero_reveal",
                    "camera_push"
                ),
                (
                    "cinematic_close",
                    "slow_tracking"
                )
            ]


        elif scene_type == "horror":

            shots = [
                (
                    "dark_wide",
                    "slow_dolly"
                ),
                (
                    "close_tension",
                    "slow_zoom"
                )
            ]


        elif scene_type == "dialogue":

            shots = [
                (
                    "medium_dialogue",
                    "static_camera"
                ),
                (
                    "close_emotion",
                    "slow_push"
                )
            ]


        else:

            shots = [
                (
                    "wide_establishing",
                    "slow_tracking"
                ),
                (
                    "medium_action",
                    "camera_move"
                )
            ]


        selected = shots[
            (shot_id - 1)
            %
            len(shots)
        ]


        shot_type, movement = selected


        prompt = (
            f"{self.quality.upper()} HDR cinematic shot, "
            f"{visual}, "
            f"{action}, "
            f"{shot_type}, "
            f"{movement}, "
            "anamorphic lens, "
            "volumetric lighting, "
            "cinematic color grading"
        )


        return {

            "shot_id":
                shot_id,

            "start":
                round(start,2),

            "duration":
                round(duration,2),


            "camera": {

                "type":
                    "cinematic",

                "shot_type":
                    shot_type,

                "movement":
                    movement
            },


            "scene_type":
                scene_type,


            "director_prompt":
                prompt
        }



    def analyze_scene(
        self,
        scene_id,
        scene_data,
        duration
    ):

        visual = scene_data.get(
            "visual",
            "unknown environment"
        )


        action = scene_data.get(
            "video",
            "cinematic movement"
        )


        scene_type = self.detect_scene_type(
            scene_data
        )


        if scene_type == "epic_space":

            shot_count = 3

        elif duration >= 10:

            shot_count = 3

        else:

            shot_count = 2


        shot_duration = (
            duration /
            shot_count
        )


        shots = []


        for i in range(
            shot_count
        ):

            shots.append(
                self.build_shot(
                    i + 1,
                    i * shot_duration,
                    shot_duration,
                    visual,
                    action,
                    scene_type
                )
            )


        result = {

            "scene_id":
                scene_id,

            "created":
                datetime.now().isoformat(),

            "quality":
                self.quality,

            "scene_type":
                scene_type,

            "duration":
                duration,

            "shot_count":
                len(shots),

            "shots":
                shots
        }


        file_path = (
            self.director_path /
            f"scene_{scene_id:03d}_director.json"
        )


        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                result,
                f,
                indent=2,
                ensure_ascii=False
            )


        return str(file_path)



    def load_direction(
        self,
        scene_id
    ):

        file_path = (
            self.director_path /
            f"scene_{scene_id:03d}_director.json"
        )


        if not file_path.exists():

            return None


        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)
