from pathlib import Path

import json
from datetime import datetime


class StoryboardEngine:
    """
    Converts AI Director decisions into storyboard format.

    StoryboardEngine does not invent cinematic decisions.
    It only normalizes the director contract for rendering.
    """

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
            exist_ok=True,
        )

        self.director_path.mkdir(
            parents=True,
            exist_ok=True,
        )


    def create_storyboard_from_director(
        self,
        scene_id,
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


        shots = []

        for shot in director_data.get(
            "shots",
            [],
        ):

            shots.append(
                {
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
            )


        storyboard = {

            "scene_id":
                scene_id,

            "created":
                datetime.now().isoformat(),

            "source":
                "AI Director",

            "quality":
                director_data.get(
                    "quality",
                    "8k",
                ),

            "scene_type":
                director_data.get(
                    "scene_type",
                    "cinematic",
                ),

            "duration":
                director_data.get(
                    "duration",
                    0,
                ),

            "shot_count":
                len(shots),

            "shots":
                shots,
        }


        scene_folder = (
            self.storyboard_path /
            f"scene_{scene_id:03d}"
        )

        scene_folder.mkdir(
            parents=True,
            exist_ok=True,
        )


        file = (
            scene_folder /
            "storyboard.json"
        )


        file.write_text(
            json.dumps(
                storyboard,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


        return file


    def create_storyboard(
        self,
        scene_id,
        scene_data,
        duration,
    ):
        """
        Compatibility wrapper.

        Existing callers continue working,
        but storyboard generation is delegated
        to AI Director output.
        """

        return self.create_storyboard_from_director(
            scene_id
        )
