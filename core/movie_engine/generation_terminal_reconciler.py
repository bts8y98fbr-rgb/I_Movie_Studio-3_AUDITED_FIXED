from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

from core.ai_core.generation_job_repository import (
    GenerationJobRepositoryError,
)
from core.movie_engine.generation_status import (
    aggregate_generation_tasks,
)


class GenerationTerminalReconciliationError(RuntimeError):
    """Raised when a failed or cancelled job cannot reconcile locally."""


class GenerationTerminalReconciler:
    ELIGIBLE_TERMINAL_STATUSES = {
        "failed",
        "cancelled",
    }
    ALLOWED_PRE_TERMINAL_STATUSES = {
        "waiting",
        "processing",
        "submitted",
        "running",
        "succeeded",
    }
    PROHIBITED_RESULT_KEYS = {
        "asset_id",
        "asset_file",
        "registry_version",
        "provider_result",
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
        requested_task_id = str(task_id)
        submitted = self._load_submitted(
            requested_task_id
        )
        self._require_requested_identity(
            submitted,
            requested_task_id,
            "submitted",
        )

        terminal = self._load_terminal(
            requested_task_id
        )
        self._require_requested_identity(
            terminal,
            requested_task_id,
            "terminal",
        )
        self._validate_terminal_status(
            terminal
        )
        self._validate_cross_record_identity(
            submitted,
            terminal,
        )
        self._validate_chain(
            requested_task_id
        )

        generation_path = self._generation_result_path(
            terminal
        )
        document = self._load_generation_result(
            generation_path
        )
        task_index = self._validate_scene(
            document,
            terminal,
        )

        updated = deepcopy(document)
        task = updated["tasks"][task_index]
        self._apply_terminal(
            task,
            terminal,
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
            requested_task_id,
            updated,
            terminal["status"],
        )

        return updated

    def _load_submitted(self, task_id):
        try:
            return self.job_repository.resume(
                task_id
            )
        except GenerationJobRepositoryError as exc:
            raise GenerationTerminalReconciliationError(
                "Submitted generation job record is missing, "
                f"invalid, or corrupt: {exc}"
            ) from exc

    def _load_terminal(self, task_id):
        try:
            if not self.job_repository.terminal_exists(
                task_id
            ):
                raise GenerationTerminalReconciliationError(
                    "Terminal generation job record is missing"
                )
            return self.job_repository.load_terminal(
                task_id
            )
        except GenerationTerminalReconciliationError:
            raise
        except GenerationJobRepositoryError as exc:
            raise GenerationTerminalReconciliationError(
                "Terminal generation job record is invalid or corrupt: "
                f"{exc}"
            ) from exc

    def _require_requested_identity(
        self,
        record,
        requested_task_id,
        label,
    ):
        if record.get("task_id") != requested_task_id:
            raise GenerationTerminalReconciliationError(
                f"{label.capitalize()} task identity mismatch"
            )

    def _validate_terminal_status(self, terminal):
        status = terminal.get("status")
        if status not in self.ELIGIBLE_TERMINAL_STATUSES:
            raise GenerationTerminalReconciliationError(
                "Terminal generation job status is not eligible "
                f"for failed/cancelled reconciliation: {status!r}"
            )

    def _validate_cross_record_identity(
        self,
        submitted,
        terminal,
    ):
        for field in (
            "task_id",
            "task_type",
            "job_id",
            "provider",
            "metadata",
        ):
            if submitted.get(field) != terminal.get(field):
                raise GenerationTerminalReconciliationError(
                    "Submitted/terminal generation identity mismatch: "
                    f"{field}"
                )

    def _validate_chain(self, task_id):
        try:
            retrieved = self.job_repository.retrieved_exists(
                task_id
            )
            finalized = self.job_repository.finalized_exists(
                task_id
            )
        except GenerationJobRepositoryError as exc:
            raise GenerationTerminalReconciliationError(
                "Generation job durable chain is invalid: "
                f"{exc}"
            ) from exc

        if retrieved or finalized:
            raise GenerationTerminalReconciliationError(
                "Failed/cancelled terminal chain contradicts "
                "retrieved or finalized state"
            )

    def _generation_result_path(self, terminal):
        metadata = terminal.get("metadata")
        if not isinstance(metadata, dict):
            raise GenerationTerminalReconciliationError(
                "Terminal generation metadata is invalid"
            )

        scene_id = metadata.get("scene_id")
        if (
            isinstance(scene_id, bool)
            or not isinstance(scene_id, int)
            or scene_id < 1
        ):
            raise GenerationTerminalReconciliationError(
                "Terminal scene identity is invalid or unsafe"
            )

        return (
            self.project_path
            / "render_output"
            / f"scene_{scene_id:03d}"
            / "generation_result.json"
        )

    def _load_generation_result(self, path):
        if not path.is_file():
            raise GenerationTerminalReconciliationError(
                "generation_result scene document is missing"
            )

        try:
            raw = path.read_bytes()
            document = json.loads(
                raw.decode("utf-8")
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise GenerationTerminalReconciliationError(
                "generation_result scene document is invalid JSON"
            ) from exc

        if not isinstance(document, dict):
            raise GenerationTerminalReconciliationError(
                "generation_result scene document must be a dictionary"
            )

        return document

    def _validate_scene(
        self,
        document,
        terminal,
    ):
        if (
            document.get("scene_id")
            != terminal["metadata"]["scene_id"]
        ):
            raise GenerationTerminalReconciliationError(
                "Scene identity mismatch in generation_result"
            )

        tasks = document.get("tasks")
        if not isinstance(tasks, list):
            raise GenerationTerminalReconciliationError(
                "generation_result task collection must be a list"
            )

        matches = [
            index
            for index, task in enumerate(tasks)
            if (
                isinstance(task, dict)
                and task.get("task_id")
                == terminal["task_id"]
            )
        ]
        if len(matches) != 1:
            raise GenerationTerminalReconciliationError(
                "Generation task cardinality must be exactly one"
            )

        task = tasks[matches[0]]
        self._validate_task_identity(
            task,
            terminal,
        )
        self._validate_task_state(
            task,
            terminal,
        )

        return matches[0]

    def _validate_task_identity(
        self,
        task,
        terminal,
    ):
        for task_field, terminal_field in (
            ("task_id", "task_id"),
            ("type", "task_type"),
            ("provider", "provider"),
        ):
            if task.get(task_field) != terminal[terminal_field]:
                raise GenerationTerminalReconciliationError(
                    "Local task identity mismatch: "
                    f"{task_field}"
                )

        metadata = task.get("metadata")
        if not isinstance(metadata, dict):
            raise GenerationTerminalReconciliationError(
                "Local task metadata must be a dictionary"
            )

        for field in ("scene_id", "shot_id"):
            if (
                metadata.get(field)
                != terminal["metadata"].get(field)
            ):
                raise GenerationTerminalReconciliationError(
                    "Local task identity mismatch: "
                    f"{field}"
                )

    def _validate_task_state(
        self,
        task,
        terminal,
    ):
        result = task.get("result")
        if result is not None and not isinstance(result, dict):
            raise GenerationTerminalReconciliationError(
                "Local task result shape must be a dictionary or None"
            )

        if isinstance(result, dict):
            self._validate_result(
                result,
                terminal,
            )

        if task.get("output") is not None:
            raise GenerationTerminalReconciliationError(
                "Local task output contradicts failed/cancelled terminal"
            )

        local_status = task.get("status")
        terminal_status = terminal["status"]

        if local_status == terminal_status:
            self._validate_same_terminal(
                task,
                terminal,
            )
            return

        if local_status not in self.ALLOWED_PRE_TERMINAL_STATUSES:
            raise GenerationTerminalReconciliationError(
                "Local task status is done, opposite terminal, "
                f"unknown, or contradictory: {local_status!r}"
            )

        if isinstance(result, dict) and "status" in result:
            if result["status"] not in self.ALLOWED_PRE_TERMINAL_STATUSES:
                raise GenerationTerminalReconciliationError(
                    "Local task result status is contradictory or unknown: "
                    f"{result['status']!r}"
                )

    def _validate_result(
        self,
        result,
        terminal,
    ):
        for field in ("job_id", "provider"):
            if (
                field in result
                and result[field] != terminal[field]
            ):
                raise GenerationTerminalReconciliationError(
                    "Local task result identity mismatch: "
                    f"{field}"
                )

        if result.get("asset_ready") is True:
            raise GenerationTerminalReconciliationError(
                "Local task result contains contradictory ready asset"
            )

        if result.get("result_state") == "finalized":
            raise GenerationTerminalReconciliationError(
                "Local task result contains contradictory finalized state"
            )

        present = self.PROHIBITED_RESULT_KEYS.intersection(
            result
        )
        if present:
            raise GenerationTerminalReconciliationError(
                "Local task result contains prohibited success or asset "
                f"evidence: {sorted(present)!r}"
            )

    def _validate_same_terminal(
        self,
        task,
        terminal,
    ):
        result = task.get("result")
        expected = self._canonical_overlay(
            terminal
        )
        if not isinstance(result, dict):
            raise GenerationTerminalReconciliationError(
                "Same-terminal task result is not canonical"
            )

        for field, value in expected.items():
            if result.get(field) != value:
                raise GenerationTerminalReconciliationError(
                    "Same-terminal task result is contradictory: "
                    f"{field}"
                )

    def _canonical_overlay(self, terminal):
        return {
            "status": terminal["status"],
            "job_id": terminal["job_id"],
            "provider": terminal["provider"],
            "asset_ready": False,
        }

    def _apply_terminal(
        self,
        task,
        terminal,
    ):
        if task.get("status") == terminal["status"]:
            return

        result = task.get("result")
        if result is None:
            result = {}
        result.update(
            self._canonical_overlay(
                terminal
            )
        )
        task["result"] = result
        task["status"] = terminal["status"]
        task["output"] = None

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
            raise GenerationTerminalReconciliationError(
                "Atomic generation_result write or replace failed"
            ) from exc

    def _record_observability(
        self,
        task_id,
        document,
        terminal_status,
    ):
        data = {
            "task_id": task_id,
            "scene_id": document["scene_id"],
            "status": terminal_status,
        }

        if self.audit is not None:
            try:
                self.audit.record(
                    "generation_terminal_reconciled",
                    data,
                )
            except Exception:
                pass

        if self.events is not None:
            try:
                self.events.emit(
                    "generation_terminal_reconciled",
                    data,
                )
            except Exception:
                pass
