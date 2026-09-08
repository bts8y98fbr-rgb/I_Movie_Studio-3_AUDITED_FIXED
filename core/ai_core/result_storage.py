from datetime import datetime
from pathlib import Path
import json

from core.ai_core.asset_registry import (
    AssetRegistry,
    AssetRegistryError,
)


class AIResultStorage:

    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )

        self.asset_path = (
            self.project_path
            / "assets"
        )

        self.asset_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.registry = AssetRegistry(
            self.project_path
        )

    def save_result(
        self,
        task
    ):

        metadata = dict(
            task.metadata or {}
        )

        task_type = task.task_type

        scene_id = metadata.get(
            "scene_id",
            0
        )

        shot_id = metadata.get(
            "shot_id",
            0
        )

        asset_id = (
            task.result.get(
                "asset_id",
                task.task_id,
            )
            if isinstance(
                task.result,
                dict
            )
            else task.task_id
        )

        model_selection = metadata.get(
            "shot_model_selection",
            {},
        )

        asset_record = {

            "asset_id":
                asset_id,

            "type":
                task_type,

            "provider":
                task.provider.name,

            "model":
                model_selection,

            "quality":
                task.quality,

            "metadata":
                metadata,

            "status":
                task.status,

            "created":
                datetime.now().isoformat(),

        }

        registry_record = (
            self.registry.register(
                asset_record
            )
        )

        asset_dir = (
            self.asset_path
            / task_type
            / f"scene_{int(scene_id):03d}"
            / f"shot_{int(shot_id):03d}"
        )

        asset_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        asset_file = (
            asset_dir
            / "asset.json"
        )

        data = {

            "asset_id":
                asset_id,

            "type":
                task_type,

            "prompt":
                task.prompt,

            "provider":
                task.provider.name,

            "model":
                model_selection,

            "quality":
                task.quality,

            "status":
                task.status,

            "created":
                datetime.now().isoformat(),

            "registry":
                registry_record,

            "metadata":
                metadata,

            "result":
                task.result,

        }

        asset_file.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return asset_file

    def save_retrieved_result(
        self,
        *,
        task_id,
        job_id,
        task_type,
        provider,
        metadata,
        provider_result,
        asset_id,
        prompt,
        quality,
        model_selection=None,
    ):

        metadata = dict(
            metadata or {}
        )

        scene_id = metadata.get(
            "scene_id"
        )
        shot_id = metadata.get(
            "shot_id"
        )

        generation_context = {
            "task_id": task_id,
            "job_id": job_id,
            "source": "remote_retrieval",
        }

        model_selection = dict(
            model_selection or {}
        )

        asset_record = {
            "asset_id": asset_id,
            "type": task_type,
            "provider": provider,
            "model": model_selection,
            "quality": quality,
            "routing": {},
            "provider_capabilities": {},
            "generation_context":
                generation_context,
            "metadata": metadata,
            "status": "generated",
        }

        existing_owner = (
            self.registry.validate_retrieved_ownership(
                asset_id,
                task_id,
            )
        )

        asset_dir = (
            self.asset_path
            / task_type
            / f"scene_{int(scene_id):03d}"
            / f"shot_{int(shot_id):03d}"
        )

        asset_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        asset_file = (
            asset_dir
            / "asset.json"
        )

        existing_asset = None

        if asset_file.is_file():

            try:
                existing_asset = json.loads(
                    asset_file.read_text(
                        encoding="utf-8"
                    )
                )
            except (
                OSError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                raise AssetRegistryError(
                    "Existing task-owned asset file is corrupt"
                ) from exc

            self._validate_existing_retrieved_asset(
                existing_asset,
                task_id=task_id,
                job_id=job_id,
                task_type=task_type,
                provider=provider,
                metadata=metadata,
                provider_result=provider_result,
                asset_id=asset_id,
            )

        created = (
            existing_asset.get("created")
            if isinstance(
                existing_asset,
                dict
            )
            else datetime.now().isoformat()
        )

        provisional = {
            "asset_id": asset_id,
            "type": task_type,
            "prompt": prompt,
            "provider": provider,
            "model": model_selection,
            "quality": quality,
            "status": "generated",
            "created": created,
            "registry": (
                existing_owner
                if existing_owner is not None
                else {}
            ),
            "metadata": metadata,
            "generation_context":
                generation_context,
            "result": provider_result,
        }

        if existing_asset is None:
            self._write_asset(
                asset_file,
                provisional,
            )

        registry_record = (
            self.registry.ensure_retrieved_registration(
                asset_record
            )
        )

        final_data = dict(
            provisional
        )
        final_data["registry"] = (
            registry_record
        )

        self._write_asset(
            asset_file,
            final_data,
        )

        return asset_file

    def _validate_existing_retrieved_asset(
        self,
        existing,
        *,
        task_id,
        job_id,
        task_type,
        provider,
        metadata,
        provider_result,
        asset_id,
    ):

        if not isinstance(existing, dict):
            raise AssetRegistryError(
                "Existing retrieved asset must be a dictionary"
            )

        for field, expected in (
            ("asset_id", asset_id),
            ("type", task_type),
            ("provider", provider),
        ):
            if existing.get(field) != expected:
                raise AssetRegistryError(
                    "Existing retrieved asset identity conflict: "
                    f"{field}"
                )

        existing_metadata = existing.get(
            "metadata",
            {},
        )

        for field in (
            "scene_id",
            "shot_id",
        ):
            if (
                existing_metadata.get(field)
                != metadata.get(field)
            ):
                raise AssetRegistryError(
                    "Existing retrieved asset metadata conflict: "
                    f"{field}"
                )

        existing_context = existing.get(
            "generation_context",
            {},
        )

        expected_context = {
            "task_id": task_id,
            "job_id": job_id,
            "source": "remote_retrieval",
        }

        if existing_context != expected_context:
            raise AssetRegistryError(
                "Existing retrieved asset ownership conflict"
            )

        if (
            "result" in existing
            and existing.get("result")
            != provider_result
        ):
            raise AssetRegistryError(
                "Existing retrieved asset result conflicts "
                "with durable retrieved result"
            )

    def _write_asset(
        self,
        asset_file,
        data,
    ):

        Path(asset_file).write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
