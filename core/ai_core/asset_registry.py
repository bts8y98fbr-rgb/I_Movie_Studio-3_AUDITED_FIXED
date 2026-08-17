from datetime import datetime
import json
from pathlib import Path


class AssetRegistry:

    def __init__(self, project_path):

        self.project_path = Path(
            project_path
        )

        self.registry_file = (
            self.project_path
            / "assets"
            / "registry.json"
        )

        self.registry_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.registry_file.exists():

            self.registry_file.write_text(
                json.dumps(
                    [],
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )


    def _load(self):

        return json.loads(
            self.registry_file.read_text(
                encoding="utf-8"
            )
        )


    def _save(
        self,
        assets
    ):

        self.registry_file.write_text(
            json.dumps(
                assets,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


    def register(
        self,
        asset
    ):

        assets = self._load()


        record = {

            "asset_id":
                asset.get(
                    "asset_id"
                ),

            "type":
                asset.get(
                    "type"
                ),

            "provider":
                asset.get(
                    "provider"
                ),

            "model":
                asset.get(
                    "model",
                    {},
                ),

            "metadata":
                asset.get(
                    "metadata",
                    {},
                ),

            "asset_path":
                asset.get(
                    "asset_path"
                ),

            "created":
                datetime.now().isoformat(),

        }


        assets.append(
            record
        )


        self._save(
            assets
        )


        return record



    def list_assets(
        self
    ):

        return self._load()



    def get_asset(
        self,
        asset_id
    ):

        assets = self._load()


        for asset in assets:

            if asset.get(
                "asset_id"
            ) == asset_id:

                return asset


        return None



    def find_by_scene(
        self,
        scene_id
    ):

        assets = self._load()


        return [

            asset

            for asset in assets

            if asset.get(
                "metadata",
                {}
            ).get(
                "scene_id"
            ) == scene_id

        ]



    def find_by_shot(
        self,
        shot_id
    ):

        assets = self._load()


        return [

            asset

            for asset in assets

            if asset.get(
                "metadata",
                {}
            ).get(
                "shot_id"
            ) == shot_id

        ]



    def find_by_type(
        self,
        asset_type
    ):

        assets = self._load()


        return [

            asset

            for asset in assets

            if asset.get(
                "type"
            ) == asset_type

        ]



    def remove_asset(
        self,
        asset_id
    ):

        assets = self._load()


        filtered = [

            asset

            for asset in assets

            if asset.get(
                "asset_id"
            ) != asset_id

        ]


        removed = (
            len(filtered)
            != len(assets)
        )


        self._save(
            filtered
        )


        return removed
