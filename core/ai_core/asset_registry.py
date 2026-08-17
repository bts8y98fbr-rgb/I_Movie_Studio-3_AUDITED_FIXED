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


    def _save(self, assets):

        self.registry_file.write_text(
            json.dumps(
                assets,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


    def register(self, asset):

        assets = self._load()

        record = {
            "asset_id": asset.get(
                "asset_id"
            ),
            "type": asset.get(
                "type"
            ),
            "provider": asset.get(
                "provider"
            ),
            "model": asset.get(
                "model",
                {},
            ),
            "metadata": asset.get(
                "metadata",
                {},
            ),
            "asset_path": asset.get(
                "asset_path"
            ),
            "created": datetime.now().isoformat(),
        }


        assets.append(record)

        self._save(
            assets
        )

        return record


    def list_assets(self):

        return self._load()
