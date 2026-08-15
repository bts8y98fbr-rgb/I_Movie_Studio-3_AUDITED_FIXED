from pathlib import Path
import json
from datetime import datetime
import uuid


class AssetGenerator:


    def __init__(
        self,
        project_path="projects/test_movie"
    ):

        self.project_path = Path(project_path)

        self.asset_path = (
            self.project_path /
            "assets"
        )

        self.asset_path.mkdir(
            parents=True,
            exist_ok=True
        )



    def create_asset(
        self,
        asset_type: str,
        prompt: str,
        quality="8k",
        metadata=None
    ):

        if metadata is None:
            metadata = {}


        asset_id = str(
            uuid.uuid4()
        )[:8]


        scene_id = metadata.get(
            "scene_id",
            "unknown"
        )

        shot_id = metadata.get(
            "shot_id",
            "unknown"
        )


        if isinstance(scene_id, int):

            asset_dir = (
                self.asset_path /
                asset_type /
                f"scene_{scene_id:03d}"
            )

        else:

            asset_dir = (
                self.asset_path /
                asset_type /
                str(scene_id)
            )


        if shot_id != "unknown":

            asset_dir = (
                asset_dir /
                f"shot_{shot_id:03d}"
            )


        asset_dir.mkdir(
            parents=True,
            exist_ok=True
        )


        asset_file = (
            asset_dir /
            "asset.json"
        )


        asset = {

            "asset_id":
                asset_id,

            "type":
                asset_type,

            "prompt":
                prompt,

            "quality":
                quality,

            "status":
                "generated",

            "created":
                datetime.now().isoformat(),

            "metadata":
                metadata

        }


        asset_file.write_text(

            json.dumps(
                asset,
                indent=2,
                ensure_ascii=False
            ),

            encoding="utf-8"

        )


        return asset



    def generate_from_render_plan(
        self,
        render_plan: dict,
        quality="8k"
    ):

        assets = []


        for shot in render_plan.get(
            "shots",
            []
        ):


            prompt = (

                shot.get(
                    "director_prompt"
                )

                or

                shot.get(
                    "ai_prompt"
                )

                or

                shot.get(
                    "prompt"
                )

                or ""

            )


            asset = self.create_asset(

                "video",

                prompt,

                quality,

                {

                    "scene_id":
                        render_plan.get(
                            "scene_id"
                        ),

                    "shot_id":
                        shot.get(
                            "shot_id"
                        ),

                    "timeline":
                        shot.get(
                            "timeline",
                            {}
                        ),

                    "camera":
                        shot.get(
                            "camera",
                            {}
                        ),

                    "quality":
                        shot.get(
                            "quality",
                            {}
                        )

                }

            )


            assets.append(
                asset
            )


        return assets
