from datetime import datetime
import json
from pathlib import Path


class AssetRegistryError(RuntimeError):
    """Raised when local asset ownership or version state is inconsistent."""


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

        try:
            assets = json.loads(
                self.registry_file.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise AssetRegistryError(
                "Asset Registry cannot be read"
            ) from exc

        if not isinstance(assets, list):
            raise AssetRegistryError(
                "Asset Registry root must be a list"
            )

        return assets

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

    def find_by_generation_task(
        self,
        task_id,
    ):

        return [
            asset
            for asset in self._load()
            if (
                asset.get(
                    "generation_context",
                    {},
                ).get("task_id")
                == task_id
            )
        ]

    def validate_retrieved_ownership(
        self,
        asset_id,
        task_id,
    ):

        assets = self._load()

        owners = [
            asset
            for asset in assets
            if (
                asset.get(
                    "generation_context",
                    {},
                ).get("task_id")
                == task_id
            )
        ]

        if len(owners) > 1:
            raise AssetRegistryError(
                "Multiple Registry entries exist "
                f"for generation task {task_id!r}"
            )

        foreign_asset_owners = [
            asset
            for asset in assets
            if (
                asset.get("asset_id") == asset_id
                and asset.get(
                    "generation_context",
                    {},
                ).get("task_id")
                != task_id
            )
        ]

        if foreign_asset_owners:
            raise AssetRegistryError(
                f"Asset {asset_id!r} is owned by another generation task"
            )

        if owners:
            owner = owners[0]

            if owner.get("asset_id") != asset_id:
                raise AssetRegistryError(
                    "Generation task ownership conflicts "
                    "with requested asset identity"
                )

        versions = self.get_versions(
            asset_id
        )

        if not owners and len(versions) > 1:
            raise AssetRegistryError(
                "Multiple unowned Registry versions are ambiguous "
                f"for asset {asset_id!r}"
            )

        if not owners and len(versions) == 1:
            version_file = (
                self.version_root
                / asset_id
                / versions[0]
                / "asset.json"
            )

            if version_file.is_file():
                try:
                    version_data = json.loads(
                        version_file.read_text(
                            encoding="utf-8"
                        )
                    )
                except (
                    OSError,
                    TypeError,
                    json.JSONDecodeError,
                ) as exc:
                    raise AssetRegistryError(
                        "Existing Registry version is corrupt"
                    ) from exc

                version_task_id = (
                    version_data.get(
                        "generation_context",
                        {},
                    ).get("task_id")
                )

                if version_task_id != task_id:
                    raise AssetRegistryError(
                        "Existing Registry version belongs "
                        "to another generation task"
                    )

        return (
            owners[0]
            if owners
            else None
        )

    def ensure_retrieved_registration(
        self,
        asset,
    ):

        expected = self.enrich_metadata(
            asset
        )

        context = expected.get(
            "generation_context",
            {},
        )

        task_id = context.get(
            "task_id"
        )
        job_id = context.get(
            "job_id"
        )
        source = context.get(
            "source"
        )
        asset_id = expected.get(
            "asset_id"
        )

        if (
            not isinstance(task_id, str)
            or not task_id
            or not isinstance(job_id, str)
            or not job_id
            or source != "remote_retrieval"
        ):
            raise AssetRegistryError(
                "Retrieved asset generation_context is invalid"
            )

        owner = self.validate_retrieved_ownership(
            asset_id,
            task_id,
        )

        if owner is not None:

            self._assert_retrieved_compatible(
                owner,
                expected,
            )

            version = owner.get(
                "version"
            )

            if (
                isinstance(version, bool)
                or not isinstance(version, int)
                or version < 1
            ):
                raise AssetRegistryError(
                    "Existing task-owned Registry entry "
                    "has invalid version"
                )

            version_file = self._version_file(
                asset_id,
                version,
            )

            if version_file.is_file():

                version_data = self._load_version_file(
                    version_file
                )

                self._assert_retrieved_compatible(
                    version_data,
                    expected,
                )

            else:

                self._write_version_exact(
                    asset_id,
                    version,
                    owner,
                )

            return owner

        assets = self._load()
        versions = self.get_versions(
            asset_id
        )

        if versions:

            if len(versions) != 1:
                raise AssetRegistryError(
                    "Ambiguous Registry versions "
                    "for retrieved asset"
                )

            version_name = versions[0]

            if (
                not version_name.startswith("v")
                or not version_name[1:].isdigit()
            ):
                raise AssetRegistryError(
                    "Retrieved asset Registry version name is invalid"
                )

            version_number = int(
                version_name[1:]
            )

            version_file = self._version_file(
                asset_id,
                version_number,
            )

            if version_file.is_file():

                version_data = (
                    self._load_version_file(
                        version_file
                    )
                )

            else:

                version_data = dict(
                    expected
                )
                version_data["version"] = (
                    version_number
                )
                version_data["created"] = (
                    datetime.now().isoformat()
                )

                self._write_version_exact(
                    asset_id,
                    version_number,
                    version_data,
                )

            self._assert_retrieved_compatible(
                version_data,
                expected,
            )

            recovered = dict(
                version_data
            )
            recovered["version"] = (
                version_number
            )
            recovered.setdefault(
                "created",
                datetime.now().isoformat(),
            )

            assets.append(
                recovered
            )
            self._save(
                assets
            )

            return recovered

        created = dict(
            expected
        )
        created["version"] = 1
        created["created"] = (
            datetime.now().isoformat()
        )

        assets.append(
            created
        )
        self._save(
            assets
        )

        self._write_version_exact(
            asset_id,
            1,
            created,
        )

        return created

    def _assert_retrieved_compatible(
        self,
        existing,
        expected,
    ):

        for field in (
            "asset_id",
            "type",
            "provider",
        ):
            if (
                existing.get(field)
                != expected.get(field)
            ):
                raise AssetRegistryError(
                    "Retrieved asset Registry identity conflict: "
                    f"{field}"
                )

        existing_metadata = existing.get(
            "metadata",
            {},
        )
        expected_metadata = expected.get(
            "metadata",
            {},
        )

        for field in (
            "scene_id",
            "shot_id",
        ):
            if (
                existing_metadata.get(field)
                != expected_metadata.get(field)
            ):
                raise AssetRegistryError(
                    "Retrieved asset Registry metadata conflict: "
                    f"{field}"
                )

        existing_context = existing.get(
            "generation_context",
            {},
        )
        expected_context = expected.get(
            "generation_context",
            {},
        )

        for field in (
            "task_id",
            "job_id",
            "source",
        ):
            if (
                existing_context.get(field)
                != expected_context.get(field)
            ):
                raise AssetRegistryError(
                    "Retrieved asset Registry ownership conflict: "
                    f"{field}"
                )

    def _version_file(
        self,
        asset_id,
        version,
    ):

        return (
            self.version_root
            / asset_id
            / f"v{version:03d}"
            / "asset.json"
        )

    def _load_version_file(
        self,
        path,
    ):

        try:
            data = json.loads(
                Path(path).read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise AssetRegistryError(
                "Registry version record is corrupt"
            ) from exc

        if not isinstance(data, dict):
            raise AssetRegistryError(
                "Registry version record must be a dictionary"
            )

        return data

    def _write_version_exact(
        self,
        asset_id,
        version_number,
        data,
    ):

        version_file = self._version_file(
            asset_id,
            version_number,
        )

        version_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        version_data = dict(
            data
        )

        version_data["version"] = (
            version_number
        )

        version_file.write_text(
            json.dumps(
                version_data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return version_file

    def create_version(self, asset_id, data):

        versions = self.get_versions(
            asset_id
        )

        version_number = len(versions) + 1

        self._write_version_exact(
            asset_id,
            version_number,
            data,
        )

        return f"v{version_number:03d}"

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
