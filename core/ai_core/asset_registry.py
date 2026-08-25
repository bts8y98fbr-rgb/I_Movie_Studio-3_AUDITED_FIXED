from datetime import datetime
import json
from pathlib import Path


class AssetRegistry:

    def __init__(self, project_path):

        self.project_path = Path(project_path)

        self.asset_root = (
            self.project_path / "assets"
        )

        self.registry_file = (
            self.asset_root / "registry.json"
        )

        self.version_root = (
            self.asset_root / "versions"
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


    def _save(self, assets):

        self.registry_file.write_text(
            json.dumps(
                assets,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


    def enrich_metadata(self, asset):

        return {

            "asset_id":
                asset.get("asset_id"),

            "type":
                asset.get("type"),

            "provider":
                asset.get("provider"),

            "model":
                asset.get("model", {}),

            "quality":
                asset.get("quality", {}),

            "routing":
                asset.get("routing", {}),

            "provider_capabilities":
                asset.get(
                    "provider_capabilities",
                    {},
                ),

            "generation_context":
                asset.get(
                    "generation_context",
                    {},
                ),

            "metadata":
                asset.get(
                    "metadata",
                    {},
                ),

            "status":
                asset.get(
                    "status",
                    "generated",
                ),
        }


    def register(self, asset):

        assets = self._load()

        enriched = self.enrich_metadata(
            asset
        )

        enriched["version"] = (
            self._next_version(
                enriched["asset_id"]
            )
        )

        enriched["created"] = (
            datetime.now().isoformat()
        )

        assets.append(
            enriched
        )

        self._save(
            assets
        )

        self.create_version(
            enriched["asset_id"],
            enriched,
        )

        return enriched


    def create_version(self, asset_id, data):

        versions = self.get_versions(
            asset_id
        )

        version_number = len(versions) + 1

        version_name = (
            f"v{version_number:03d}"
        )

        version_data = dict(data)

        version_data["version"] = (
            version_number
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
            version_dir / "asset.json"
        )

        version_file.write_text(
            json.dumps(
                version_data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return version_name


    def get_versions(self, asset_id):

        folder = (
            self.version_root / asset_id
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


    def get_latest_version(self, asset_id):

        versions = self.get_versions(
            asset_id
        )

        if not versions:

            return None

        return versions[-1]


    def _next_version(self, asset_id):

        return (
            len(
                self.get_versions(
                    asset_id
                )
            ) + 1
        )


    def list_assets(self):

        return self._load()


    def get_asset(self, asset_id):

        assets = [

            asset

            for asset in self._load()

            if asset.get(
                "asset_id"
            ) == asset_id

        ]

        if not assets:

            return None

        return assets[-1]


    def find_by_scene(self, scene_id):

        result = []

        for asset in self._load():

            metadata = asset.get(
                "metadata",
                {}
            )

            if metadata.get(
                "scene_id"
            ) == scene_id:

                result.append(asset)

        return result


    def find_by_shot(self, shot_id):

        result = []

        for asset in self._load():

            metadata = asset.get(
                "metadata",
                {}
            )

            if metadata.get(
                "shot_id"
            ) == shot_id:

                result.append(asset)

        return result


    def find_by_type(self, asset_type):

        return [

            asset

            for asset in self._load()

            if asset.get(
                "type"
            ) == asset_type

        ]


    def remove_asset(self, asset_id):

        assets = self._load()

        filtered = [

            asset

            for asset in assets

            if asset.get(
                "asset_id"
            ) != asset_id

        ]

        if len(filtered) == len(assets):

            return False

        self._save(
            filtered
        )

        return True
