from pathlib import Path
from datetime import datetime
import json


class AIResultStorage:


    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )


        self.asset_path = (

            self.project_path /
            "assets"

        )


        self.asset_path.mkdir(
            parents=True,
            exist_ok=True
        )



    def save_result(
        self,
        task
    ):


        metadata = task.metadata or {}


        task_type = task.task_type


        scene_id = metadata.get(
            "scene_id",
            0
        )


        shot_id = metadata.get(
            "shot_id",
            0
        )



        asset_dir = (

            self.asset_path /
            task_type /
            f"scene_{int(scene_id):03d}" /
            f"shot_{int(shot_id):03d}"

        )


        asset_dir.mkdir(
            parents=True,
            exist_ok=True
        )



        asset_file = (

            asset_dir /
            "asset.json"

        )



        data = {


            "asset_id":
                task.task_id,


            "type":
                task_type,


            "prompt":
                task.prompt,


            "provider":
                task.provider.name,


            "quality":
                task.quality,


            "status":
                task.status,


            "created":
                datetime.now().isoformat(),


            "metadata":
                metadata,


            "result":
                task.result

        }



        asset_file.write_text(

            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),

            encoding="utf-8"

        )



        return asset_file
