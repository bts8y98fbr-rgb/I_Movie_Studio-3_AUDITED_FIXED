from pathlib import Path
import json
from datetime import datetime


class SceneManager:
    """
    Управление сценами фильма.

    Каждая сцена хранится отдельно.
    """


    def __init__(self, project_path):

        self.project_path = Path(project_path)

        self.scenes_path = (
            self.project_path /
            "scenes"
        )

        self.scenes_path.mkdir(
            parents=True,
            exist_ok=True
        )



    def create_scene(
        self,
        scene_id,
        media,
        duration
    ):

        scene_folder = (
            self.scenes_path /
            f"scene_{scene_id:03d}"
        )


        scene_folder.mkdir(
            parents=True,
            exist_ok=True
        )


        data = {

            "scene_id": scene_id,

            "duration": float(duration),

            "created":
                datetime.now().isoformat(),

            "media": media

        }


        file = (
            scene_folder /
            "scene.json"
        )


        file.write_text(

            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),

            encoding="utf-8"

        )


        return file



    def load_scene(
        self,
        scene_id
    ):

        file = (

            self.scenes_path /
            f"scene_{scene_id:03d}" /
            "scene.json"

        )


        if not file.exists():

            raise FileNotFoundError(
                file
            )


        return json.loads(

            file.read_text(
                encoding="utf-8"
            )

        )



    def list_scenes(self):

        result = []


        for folder in sorted(
            self.scenes_path.glob("scene_*")
        ):

            file = (
                folder /
                "scene.json"
            )

            if file.exists():

                result.append(

                    json.loads(
                        file.read_text(
                            encoding="utf-8"
                        )
                    )

                )


        return result
