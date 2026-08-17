from datetime import datetime
import json
from pathlib import Path


class AssetRegistry:

    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )

        self.asset_root = (
            self.project_path
            / "assets"
        )

        self.registry_file = (
            self.asset_root
            / "registry.json"
        )

        self.version_root = (
            self.asset_root
            / "versions"
        )


        self.asset_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.version_root.mkdir(
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

            "version":
                self._next_version(
                    asset.get(
                        "asset_id"
                    )
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


        self.create_version(
            record["asset_id"],
            record,
        )


        return record



    def create_version(
        self,
        asset_id,
        data,
    ):

        versions = (
            self.get_versions(
                asset_id
            )
        )

        version_number = (
            len(versions) + 1
        )


        version_name = (
            f"v{version_number:03d}"
        )


        version_dir = (
            self.version_root
            / asset_id
            / version_name
        )


        version_dir.mkdir(
            parents=True,
            exist_ok=True,
        )


        version_file = (
            version_dir
            / "asset.json"
        )


        version_file.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


        return version_name



    def get_versions(
        self,
        asset_id
    ):

        folder = (
            self.version_root
            / asset_id
        )


        if not folder.exists():

            return []


        return sorted(
            [
                item.name
                for item in folder.iterdir()
                if item.is_dir()
            ]
        )



    def get_latest_version(
        self,
        asset_id
    ):

        versions = (
            self.get_versions(
                asset_id
            )
        )


        if not versions:

            return None


        return versions[-1]



    def _next_version(
        self,
        asset_id
    ):

        versions = (
            self.get_versions(
                asset_id
            )
        )

        return (
            len(versions) + 1
        )



    def list_assets(
        self
    ):

        return self._load()



    def get_asset(
        self,
        asset_id
    ):

        for asset in self._load():

            if asset.get(
                "asset_id"
            ) == asset_id:

                return asset

        return None



    def find_by_scene(
        self,
        scene_id
    ):

        return [

            asset

            for asset in self._load()

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

        return [

            asset

            for asset in self._load()

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

        return [

            asset

            for asset in self._load()

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
