from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

from core.ai_core.generation_job_asset_lifecycle import (
    GenerationJobAssetLifecycle,
)
from core.movie_engine.generation_status import (
    aggregate_generation_tasks,
)


class GenerationResultReconciliationError(RuntimeError):
    """Raised when a finalized job cannot reconcile into scene state."""


class GenerationResultReconciler:
    ALLOWED_PRE_COMPLETION_STATUSES = {
        "waiting",
        "processing",
        "submitted",
        "running",
        "succeeded",
    }
    AGGREGATION_FIELDS = (
        "generated",
        "failed",
        "cancelled",
        "submitted",
        "running",
        "pending",
        "status",
    )

    def __init__(
        self,
        job_repository,
        audit=None,
        events=None,
    ):
        self.job_repository = job_repository
        self.project_path = Path(
            job_repository.project_path
        )
        self.audit = audit
        self.events = events

    def reconcile_once(self, task_id):
        finalized = self._verify_finalized(
            task_id
        )
        generation_path = (
            self._generation_result_path(
                finalized
            )
        )
        original_bytes, document = (
            self._load_generation_result(
                generation_path
            )
        )

        task_index = self._validate_document(
            document,
            finalized,
        )
        updated = deepcopy(document)
        task = updated["tasks"][task_index]

        self._reconcile_task(
            task,
            finalized,
        )

        aggregation = aggregate_generation_tasks(
            updated["tasks"]
        )
        for field in self.AGGREGATION_FIELDS:
            updated[field] = aggregation[field]

        if updated == document:
            return updated

        self._atomic_write(
            generation_path,
            updated,
        )
        self._record_observability(
            task_id,
            updated,
        )

        return updated

    def _verify_finalized(self, task_id):
        try:
            if not self.job_repository.finalized_exists(
                task_id
            ):
                raise GenerationResultReconciliationError(
                    "Finalized generation job record is missing"
                )

            return GenerationJobAssetLifecycle(
                self.job_repository
            ).finalize_once(task_id)
        except GenerationResultReconciliationError:
            raise
        except Exception as exc:
            raise GenerationResultReconciliationError(
                "Finalized generation job state is invalid or stale: "
                f"{exc}"
            ) from exc

    def _generation_result_path(self, finalized):
        metadata = finalized.get("metadata")
        if not isinstance(metadata, dict):
            raise GenerationResultReconciliationError(
                "Finalized generation metadata is invalid"
            )

        scene_id = metadata.get("scene_id")
        if (
            isinstance(scene_id, bool)
            or not isinstance(scene_id, int)
            or scene_id < 1
        ):
            raise GenerationResultReconciliationError(
                "Finalized scene identity is invalid or unsafe"
            )

        return (
            self.project_path
            / "render_output"
            / f"scene_{scene_id:03d}"
            / "generation_result.json"
        )

    def _load_generation_result(self, path):
        if not path.is_file():
            raise GenerationResultReconciliationError(
                "generation_result scene document is missing"
            )

        try:
            original = path.read_bytes()
            document = json.loads(
                original.decode("utf-8")
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise GenerationResultReconciliationError(
                "generation_result scene document is invalid JSON"
            ) from exc

        if not isinstance(document, dict):
            raise GenerationResultReconciliationError(
                "generation_result scene document must be a dictionary"
            )

        return original, document

    def _validate_document(
        self,
        document,
        finalized,
    ):
        metadata = finalized["metadata"]
        if document.get("scene_id") != metadata["scene_id"]:
            raise GenerationResultReconciliationError(
                "Scene identity mismatch in generation_result"
            )

        tasks = document.get("tasks")
        if not isinstance(tasks, list):
            raise GenerationResultReconciliationError(
                "generation_result task collection is invalid"
            )

        matches = [
            index
            for index, task in enumerate(tasks)
            if (
                isinstance(task, dict)
                and task.get("task_id")
                == finalized["task_id"]
            )
        ]
        if len(matches) != 1:
            raise GenerationResultReconciliationError(
                "Generation task cardinality must be exactly one"
            )

        task = tasks[matches[0]]
        self._validate_task_identity(
            task,
            finalized,
        )
        self._validate_result_shape_and_identity(
            task,
            finalized,
        )
        self._validate_task_status(
            task,
            finalized,
        )

        return matches[0]

    def _validate_task_identity(
        self,
        task,
        finalized,
    ):
        for field, finalized_field in (
            ("task_id", "task_id"),
            ("type", "task_type"),
            ("provider", "provider"),
        ):
            if task.get(field) != finalized[finalized_field]:
                raise GenerationResultReconciliationError(
                    "Generation task identity mismatch: "
                    f"{field}"
                )

        task_metadata = task.get("metadata")
        if not isinstance(task_metadata, dict):
            raise GenerationResultReconciliationError(
                "Generation task metadata is invalid"
            )

        for field in ("scene_id", "shot_id"):
            if (
                task_metadata.get(field)
                != finalized["metadata"].get(field)
            ):
                raise GenerationResultReconciliationError(
                    "Generation task identity mismatch: "
                    f"{field}"
                )

    def _validate_result_shape_and_identity(
        self,
        task,
        finalized,
    ):
        result = task.get("result")
        if result is not None and not isinstance(result, dict):
            raise GenerationResultReconciliationError(
                "Generation task result shape must be a dictionary or None"
            )

        if not isinstance(result, dict):
            return

        for field in ("job_id", "provider"):
            if (
                field in result
                and result[field] != finalized[field]
            ):
                raise GenerationResultReconciliationError(
                    "Generation task result identity mismatch: "
                    f"{field}"
                )

    def _validate_task_status(
        self,
        task,
        finalized,
    ):
        status = task.get("status")
        if status == "done":
            self._validate_done_task(
                task,
                finalized,
            )
            return

        if status not in self.ALLOWED_PRE_COMPLETION_STATUSES:
            raise GenerationResultReconciliationError(
                "Generation task status is failed, cancelled, "
                f"unknown, or contradictory: {status!r}"
            )

    def _completion_overlay(self, finalized):
        return {
            "status": "done",
            "job_id": finalized["job_id"],
            "provider": finalized["provider"],
            "asset_id": finalized["asset_id"],
            "asset_ready": True,
            "result_state": "finalized",
            "asset_file": finalized["asset_file"],
            "registry_version": finalized[
                "registry_version"
            ],
        }

    def _validate_done_task(
        self,
        task,
        finalized,
    ):
        expected = self._completion_overlay(
            finalized
        )
        if task.get("output") != finalized["asset_file"]:
            raise GenerationResultReconciliationError(
                "Done task output conflicts with finalized asset"
            )

        result = task.get("result")
        if not isinstance(result, dict):
            raise GenerationResultReconciliationError(
                "Done task result is not a canonical completion dictionary"
            )

        for field, value in expected.items():
            if result.get(field) != value:
                raise GenerationResultReconciliationError(
                    "Done task completion result conflict: "
                    f"{field}"
                )

    def _reconcile_task(
        self,
        task,
        finalized,
    ):
        if task.get("status") == "done":
            return

        result = task.get("result")
        if result is None:
            result = {}

        result.update(
            self._completion_overlay(
                finalized
            )
        )
        task["result"] = result
        task["status"] = "done"
        task["output"] = finalized["asset_file"]

    def _atomic_write(self, target, document):
        descriptor = None
        temporary_path = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
            ) as handle:
                descriptor = None
                json.dump(
                    document,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary_path,
                target,
            )
        except (
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            if descriptor is not None:
                os.close(descriptor)
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
            raise GenerationResultReconciliationError(
                "Atomic generation_result write or replace failed"
            ) from exc

    def _record_observability(
        self,
        task_id,
        document,
    ):
        data = {
            "task_id": task_id,
            "scene_id": document["scene_id"],
            "status": document["status"],
        }

        if self.audit is not None:
            try:
                self.audit.record(
                    "generation_result_reconciled",
                    data,
                )
            except Exception:
                pass

        if self.events is not None:
            try:
                self.events.emit(
                    "generation_result_reconciled",
                    data,
                )
            except Exception:
                pass
