from datetime import datetime, timezone
import json
from pathlib import Path

from core.ai_core.generation_job_repository import (
    GenerationJobRepositoryError,
)
from core.ai_core.result_storage import (
    AIResultStorage,
)


class GenerationJobAssetLifecycleError(RuntimeError):
    """Raised when durable local asset finalization cannot proceed."""


class GenerationJobAssetLifecycle:

    IDENTITY_FIELDS = (
        "task_id",
        "task_type",
        "job_id",
        "provider",
        "metadata",
    )

    def __init__(
        self,
        job_repository,
        audit=None,
        events=None,
    ):
        self.job_repository = (
            job_repository
        )
        self.project_path = Path(
            job_repository.project_path
        )
        self.audit = audit
        self.events = events

    def finalize_once(
        self,
        task_id,
    ):

        existing = (
            self._load_existing_finalized(
                task_id
            )
        )

        if existing is not None:

            self._verify_materialized_state(
                task_id=existing["task_id"],
                job_id=existing["job_id"],
                task_type=existing["task_type"],
                provider=existing["provider"],
                metadata=existing["metadata"],
                asset_id=existing["asset_id"],
                asset_file=existing["asset_file"],
                registry_version=(
                    existing["registry_version"]
                ),
            )

            return existing

        receipt = self._load_receipt(
            task_id
        )
        terminal = self._load_terminal(
            task_id
        )
        retrieved = self._load_retrieved(
            task_id
        )

        self._validate_source_chain(
            receipt,
            terminal,
            retrieved,
        )

        asset_id = self._select_asset_id(
            retrieved["provider_result"],
            task_id,
        )

        local_context = (
            self._load_local_context(
                receipt
            )
        )

        storage = AIResultStorage(
            self.project_path
        )

        try:
            asset_file = (
                storage.save_retrieved_result(
                    task_id=receipt["task_id"],
                    job_id=receipt["job_id"],
                    task_type=receipt["task_type"],
                    provider=receipt["provider"],
                    metadata=dict(
                        receipt["metadata"]
                    ),
                    provider_result=dict(
                        retrieved[
                            "provider_result"
                        ]
                    ),
                    asset_id=asset_id,
                    prompt=local_context[
                        "prompt"
                    ],
                    quality=local_context[
                        "quality"
                    ],
                    model_selection=(
                        local_context[
                            "model_selection"
                        ]
                    ),
                )
            )
        except Exception as exc:
            raise GenerationJobAssetLifecycleError(
                "Asset storage finalization failed: "
                f"{exc}"
            ) from exc

        (
            verified_asset_file,
            registry_record,
        ) = self._verify_materialized_state(
            task_id=receipt["task_id"],
            job_id=receipt["job_id"],
            task_type=receipt["task_type"],
            provider=receipt["provider"],
            metadata=receipt["metadata"],
            asset_id=asset_id,
            asset_file=asset_file,
            registry_version=None,
        )

        try:
            asset_file_value = str(
                verified_asset_file.resolve().relative_to(
                    self.project_path.resolve()
                )
            )
        except ValueError:
            raise GenerationJobAssetLifecycleError(
                "Finalized asset file escaped project boundary"
            )

        finalized = {
            "format_version":
                self.job_repository.FORMAT_VERSION,
            "task_id":
                receipt["task_id"],
            "task_type":
                receipt["task_type"],
            "job_id":
                receipt["job_id"],
            "provider":
                receipt["provider"],
            "metadata":
                dict(receipt["metadata"]),
            "result_state":
                "finalized",
            "asset_ready":
                True,
            "asset_id":
                asset_id,
            "asset_file":
                asset_file_value,
            "registry_version":
                registry_record["version"],
            "finalized_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }

        try:
            durable = (
                self.job_repository.persist_finalized(
                    finalized
                )
            )
        except Exception as exc:
            raise GenerationJobAssetLifecycleError(
                "Cannot persist durable finalized generation "
                f"job record: {exc}"
            ) from exc

        self._record_observability(
            durable
        )

        return durable

    def _load_existing_finalized(
        self,
        task_id,
    ):

        try:
            if not self.job_repository.finalized_exists(
                task_id
            ):
                return None

            return self.job_repository.load_finalized(
                task_id
            )
        except GenerationJobRepositoryError as exc:
            raise GenerationJobAssetLifecycleError(
                "Cannot load finalized generation job record: "
                f"{exc}"
            ) from exc

    def _load_receipt(
        self,
        task_id,
    ):

        try:
            return self.job_repository.resume(
                task_id
            )
        except GenerationJobRepositoryError as exc:
            raise GenerationJobAssetLifecycleError(
                "Cannot load submitted generation job receipt: "
                f"{exc}"
            ) from exc

    def _load_terminal(
        self,
        task_id,
    ):

        try:
            if not self.job_repository.terminal_exists(
                task_id
            ):
                raise GenerationJobAssetLifecycleError(
                    "Successful terminal generation job record "
                    "is required before asset finalization"
                )

            return self.job_repository.load_terminal(
                task_id
            )
        except GenerationJobAssetLifecycleError:
            raise
        except GenerationJobRepositoryError as exc:
            raise GenerationJobAssetLifecycleError(
                "Cannot load terminal generation job record: "
                f"{exc}"
            ) from exc

    def _load_retrieved(
        self,
        task_id,
    ):

        try:
            if not self.job_repository.retrieved_exists(
                task_id
            ):
                raise GenerationJobAssetLifecycleError(
                    "Retrieved generation job record "
                    "is missing before asset finalization"
                )

            return self.job_repository.load_retrieved(
                task_id
            )
        except GenerationJobAssetLifecycleError:
            raise
        except GenerationJobRepositoryError as exc:
            raise GenerationJobAssetLifecycleError(
                "Cannot load retrieved generation job record: "
                f"{exc}"
            ) from exc

    def _validate_source_chain(
        self,
        receipt,
        terminal,
        retrieved,
    ):

        if terminal.get("status") != "succeeded":
            raise GenerationJobAssetLifecycleError(
                "Asset finalization requires succeeded terminal state"
            )

        if (
            terminal.get("result_state")
            != "pending_retrieval"
            or terminal.get("asset_ready") is not False
        ):
            raise GenerationJobAssetLifecycleError(
                "Terminal generation state is not eligible "
                "for finalization"
            )

        if (
            retrieved.get("result_state")
            != "retrieved"
            or retrieved.get("asset_ready") is not False
        ):
            raise GenerationJobAssetLifecycleError(
                "Retrieved generation state is not eligible "
                "for finalization"
            )

        for field in self.IDENTITY_FIELDS:

            submitted_value = receipt.get(
                field
            )

            if terminal.get(field) != submitted_value:
                raise GenerationJobAssetLifecycleError(
                    "Submitted/terminal generation identity mismatch: "
                    f"{field}"
                )

            if retrieved.get(field) != submitted_value:
                raise GenerationJobAssetLifecycleError(
                    "Submitted/retrieved generation identity mismatch: "
                    f"{field}"
                )

    def _select_asset_id(
        self,
        provider_result,
        task_id,
    ):

        if not isinstance(
            provider_result,
            dict,
        ):
            raise GenerationJobAssetLifecycleError(
                "Retrieved provider result must be a dictionary"
            )

        if "asset_id" not in provider_result:
            asset_id = task_id
        else:
            asset_id = provider_result[
                "asset_id"
            ]

        self._validate_asset_id(
            asset_id
        )

        return asset_id

    def _validate_asset_id(
        self,
        asset_id,
    ):

        if (
            not isinstance(asset_id, str)
            or not asset_id
            or not asset_id.strip()
            or asset_id != asset_id.strip()
            or asset_id in {".", ".."}
            or "/" in asset_id
            or "\\" in asset_id
            or Path(asset_id).is_absolute()
        ):
            raise GenerationJobAssetLifecycleError(
                f"Invalid or unsafe provider asset_id: {asset_id!r}"
            )

    def _load_local_context(
        self,
        receipt,
    ):

        metadata = receipt["metadata"]

        scene_id = metadata.get(
            "scene_id"
        )
        shot_id = metadata.get(
            "shot_id"
        )

        try:
            scene_number = int(
                scene_id
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise GenerationJobAssetLifecycleError(
                "Scene identity is invalid for local asset context"
            ) from exc

        generation_path = (
            self.project_path
            / "render_output"
            / f"scene_{scene_number:03d}"
            / "generation_result.json"
        )

        generation = self._read_json_file(
            generation_path,
            "generation_result",
        )

        tasks = generation.get(
            "tasks"
        )

        if not isinstance(tasks, list):
            raise GenerationJobAssetLifecycleError(
                "generation_result task collection is invalid"
            )

        matches = [
            task
            for task in tasks
            if (
                isinstance(task, dict)
                and task.get("task_id")
                == receipt["task_id"]
            )
        ]

        if len(matches) != 1:
            raise GenerationJobAssetLifecycleError(
                "Scene generation task cardinality must be exactly one "
                f"for task {receipt['task_id']!r}"
            )

        task_snapshot = matches[0]

        if (
            task_snapshot.get("type")
            != receipt["task_type"]
        ):
            raise GenerationJobAssetLifecycleError(
                "Scene task type identity mismatch"
            )

        if (
            task_snapshot.get("provider")
            != receipt["provider"]
        ):
            raise GenerationJobAssetLifecycleError(
                "Scene task provider identity mismatch"
            )

        snapshot_metadata = (
            task_snapshot.get(
                "metadata",
                {},
            )
        )

        if not isinstance(
            snapshot_metadata,
            dict,
        ):
            raise GenerationJobAssetLifecycleError(
                "Scene task metadata is invalid"
            )

        for field in (
            "scene_id",
            "shot_id",
        ):
            if (
                snapshot_metadata.get(field)
                != metadata.get(field)
            ):
                raise GenerationJobAssetLifecycleError(
                    "Scene task durable identity mismatch: "
                    f"{field}"
                )

        render_path = (
            self.project_path
            / "render"
            / f"scene_{scene_number:03d}"
            / "render_plan.json"
        )

        render_plan = self._read_json_file(
            render_path,
            "render_plan",
        )

        shots = render_plan.get(
            "shots"
        )

        if not isinstance(shots, list):
            raise GenerationJobAssetLifecycleError(
                "render_plan shot collection is invalid"
            )

        shot_matches = [
            shot
            for shot in shots
            if (
                isinstance(shot, dict)
                and shot.get("shot_id")
                == shot_id
            )
        ]

        if len(shot_matches) != 1:
            raise GenerationJobAssetLifecycleError(
                "Render plan shot cardinality must be exactly one "
                f"for shot {shot_id!r}"
            )

        shot = shot_matches[0]

        prompt = shot.get(
            "director_prompt"
        )

        if (
            not isinstance(prompt, str)
            or not prompt
        ):
            raise GenerationJobAssetLifecycleError(
                "Render plan director_prompt is missing"
            )

        model_selection = (
            snapshot_metadata.get(
                "shot_model_selection",
                {},
            )
        )

        if not isinstance(
            model_selection,
            dict,
        ):
            model_selection = {}

        return {
            "prompt": prompt,
            "quality":
                task_snapshot.get(
                    "quality"
                ),
            "model_selection":
                model_selection,
        }

    def _read_json_file(
        self,
        path,
        label,
    ):

        path = Path(path)

        if not path.is_file():
            raise GenerationJobAssetLifecycleError(
                f"Missing {label} local context: {path}"
            )

        try:
            value = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise GenerationJobAssetLifecycleError(
                f"Invalid {label} local context: {path}"
            ) from exc

        if not isinstance(value, dict):
            raise GenerationJobAssetLifecycleError(
                f"{label} local context must be a dictionary"
            )

        return value

    def _verify_materialized_state(
        self,
        *,
        task_id,
        job_id,
        task_type,
        provider,
        metadata,
        asset_id,
        asset_file,
        registry_version,
    ):

        self._validate_asset_id(
            asset_id
        )

        asset_path = Path(
            asset_file
        )

        if not asset_path.is_absolute():
            asset_path = (
                self.project_path
                / asset_path
            )

        try:
            asset_path.resolve().relative_to(
                self.project_path.resolve()
            )
        except ValueError as exc:
            raise GenerationJobAssetLifecycleError(
                "Finalized asset file is outside project boundary"
            ) from exc

        if not asset_path.is_file():
            raise GenerationJobAssetLifecycleError(
                "Finalized asset consistency error: "
                "asset file is missing"
            )

        asset = self._read_json_file(
            asset_path,
            "asset",
        )

        self._assert_asset_identity(
            asset,
            task_id=task_id,
            job_id=job_id,
            task_type=task_type,
            provider=provider,
            metadata=metadata,
            asset_id=asset_id,
            label="asset",
        )

        registry_path = (
            self.project_path
            / "assets"
            / "registry.json"
        )

        if not registry_path.is_file():
            raise GenerationJobAssetLifecycleError(
                "Finalized asset consistency error: "
                "Registry entry is missing"
            )

        try:
            registry = json.loads(
                registry_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise GenerationJobAssetLifecycleError(
                "Finalized asset Registry is invalid"
            ) from exc

        if not isinstance(registry, list):
            raise GenerationJobAssetLifecycleError(
                "Finalized asset Registry root is invalid"
            )

        owners = [
            entry
            for entry in registry
            if (
                isinstance(entry, dict)
                and entry.get(
                    "generation_context",
                    {},
                ).get("task_id")
                == task_id
            )
        ]

        if len(owners) != 1:
            raise GenerationJobAssetLifecycleError(
                "Finalized asset Registry must contain exactly "
                "one task-owned entry"
            )

        foreign_same_asset = [
            entry
            for entry in registry
            if (
                isinstance(entry, dict)
                and entry.get("asset_id")
                == asset_id
                and entry.get(
                    "generation_context",
                    {},
                ).get("task_id")
                != task_id
            )
        ]

        if foreign_same_asset:
            raise GenerationJobAssetLifecycleError(
                "Finalized asset Registry ownership conflict"
            )

        owner = owners[0]

        self._assert_asset_identity(
            owner,
            task_id=task_id,
            job_id=job_id,
            task_type=task_type,
            provider=provider,
            metadata=metadata,
            asset_id=asset_id,
            label="Registry",
        )

        version = owner.get(
            "version"
        )

        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
        ):
            raise GenerationJobAssetLifecycleError(
                "Finalized asset Registry version is invalid"
            )

        if (
            registry_version is not None
            and version != registry_version
        ):
            raise GenerationJobAssetLifecycleError(
                "Finalized record Registry version mismatch"
            )

        version_path = (
            self.project_path
            / "assets"
            / "versions"
            / asset_id
            / f"v{version:03d}"
            / "asset.json"
        )

        if not version_path.is_file():
            raise GenerationJobAssetLifecycleError(
                "Finalized asset Registry version is missing"
            )

        version_data = self._read_json_file(
            version_path,
            "Registry version",
        )

        self._assert_asset_identity(
            version_data,
            task_id=task_id,
            job_id=job_id,
            task_type=task_type,
            provider=provider,
            metadata=metadata,
            asset_id=asset_id,
            label="Registry version",
        )

        if (
            version_data.get("version")
            != version
        ):
            raise GenerationJobAssetLifecycleError(
                "Finalized asset Registry version identity mismatch"
            )

        return (
            asset_path,
            owner,
        )

    def _assert_asset_identity(
        self,
        value,
        *,
        task_id,
        job_id,
        task_type,
        provider,
        metadata,
        asset_id,
        label,
    ):

        if not isinstance(value, dict):
            raise GenerationJobAssetLifecycleError(
                f"{label} identity record is invalid"
            )

        for field, expected in (
            ("asset_id", asset_id),
            ("type", task_type),
            ("provider", provider),
        ):
            if value.get(field) != expected:
                raise GenerationJobAssetLifecycleError(
                    f"{label} identity mismatch: {field}"
                )

        value_metadata = value.get(
            "metadata",
            {},
        )

        if not isinstance(
            value_metadata,
            dict,
        ):
            raise GenerationJobAssetLifecycleError(
                f"{label} metadata is invalid"
            )

        for field in (
            "scene_id",
            "shot_id",
        ):
            if (
                value_metadata.get(field)
                != metadata.get(field)
            ):
                raise GenerationJobAssetLifecycleError(
                    f"{label} metadata identity mismatch: {field}"
                )

        context = value.get(
            "generation_context",
            {},
        )

        expected_context = {
            "task_id": task_id,
            "job_id": job_id,
            "source": "remote_retrieval",
        }

        if context != expected_context:
            raise GenerationJobAssetLifecycleError(
                f"{label} ownership identity mismatch"
            )

    def _record_observability(
        self,
        finalized,
    ):

        if self.audit is not None:
            try:
                self.audit.record(
                    "generation_job_asset_finalized",
                    dict(finalized),
                )
            except Exception:
                pass

        if self.events is not None:
            try:
                self.events.emit(
                    "generation_job_asset_finalized",
                    dict(finalized),
                )
            except Exception:
                pass
