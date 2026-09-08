from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile


class GenerationJobRepositoryError(RuntimeError):
    """Base error for submitted-generation receipt persistence."""


class GenerationJobReceiptError(GenerationJobRepositoryError):
    """Raised when a submitted-generation receipt is invalid or corrupt."""


class GenerationJobPersistenceError(GenerationJobRepositoryError):
    """Raised when a submitted-generation receipt cannot be written safely."""


class GenerationJobTerminalError(GenerationJobRepositoryError):
    """Raised when a terminal provider-job record is invalid or corrupt."""


class GenerationJobRetrievedError(GenerationJobRepositoryError):
    """Raised when a retrieved provider-result record is invalid or corrupt."""


class GenerationJobRepository:
    FORMAT_VERSION = 1
    RECEIPT_KEYS = {
        "format_version",
        "task_id",
        "task_type",
        "status",
        "job_id",
        "provider",
        "metadata",
        "submitted_at",
    }
    METADATA_KEYS = {
        "scene_id",
        "shot_id",
    }
    TERMINAL_STATUSES = {
        "succeeded",
        "failed",
        "cancelled",
    }
    TERMINAL_KEYS = {
        "format_version",
        "task_id",
        "task_type",
        "job_id",
        "provider",
        "status",
        "metadata",
        "terminal_at",
    }
    SUCCEEDED_TERMINAL_KEYS = TERMINAL_KEYS | {
        "result_state",
        "asset_ready",
    }
    RETRIEVED_KEYS = {
        "format_version",
        "task_id",
        "task_type",
        "job_id",
        "provider",
        "metadata",
        "result_state",
        "asset_ready",
        "provider_result",
        "retrieved_at",
    }

    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.submitted_dir = (
            self.project_path
            / "generation_jobs"
            / "submitted"
        )
        self.terminal_dir = (
            self.project_path
            / "generation_jobs"
            / "terminal"
        )
        self.retrieved_dir = (
            self.project_path
            / "generation_jobs"
            / "retrieved"
        )

    def receipt_path(self, task_id):
        task_id = str(task_id)

        if not task_id or Path(task_id).name != task_id:
            raise GenerationJobReceiptError(
                f"Invalid generation task identity: {task_id!r}"
            )

        return self.submitted_dir / f"{task_id}.json"

    def persist(self, task, result):
        if not isinstance(result, dict):
            raise GenerationJobReceiptError(
                "Submitted generation result must be a dictionary"
            )

        if result.get("status") != "submitted":
            raise GenerationJobReceiptError(
                "Generation job repository accepts submitted results only"
            )

        receipt = {
            "format_version": self.FORMAT_VERSION,
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": "submitted",
            "job_id": result.get("job_id"),
            "provider": getattr(task.provider, "name", None),
            "metadata": {
                "scene_id": task.metadata.get("scene_id"),
                "shot_id": task.metadata.get("shot_id"),
            },
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        self._validate(receipt)
        self._atomic_write(
            self.receipt_path(task.task_id),
            receipt,
        )

        return receipt

    def resume(self, task_id):
        path = self.receipt_path(task_id)

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GenerationJobRepositoryError(
                f"Cannot read generation job receipt: {path}"
            ) from exc

        try:
            receipt = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise GenerationJobReceiptError(
                f"Corrupt generation job receipt: {path}"
            ) from exc

        self._validate(receipt)

        return receipt

    def terminal_path(self, task_id):
        task_id = str(task_id)

        if not task_id or Path(task_id).name != task_id:
            raise GenerationJobTerminalError(
                f"Invalid terminal generation task identity: {task_id!r}"
            )

        return self.terminal_dir / f"{task_id}.json"

    def terminal_exists(self, task_id):
        return self.terminal_path(task_id).is_file()

    def load_terminal(self, task_id):
        task_id = str(task_id)
        path = self.terminal_path(task_id)

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GenerationJobRepositoryError(
                f"Cannot read terminal generation job record: {path}"
            ) from exc

        try:
            record = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise GenerationJobTerminalError(
                f"Corrupt terminal generation job record: {path}"
            ) from exc

        self._validate_terminal(record)

        if record["task_id"] != task_id:
            raise GenerationJobTerminalError(
                "Terminal generation job record task identity mismatch"
            )

        return record

    def persist_terminal(self, record):
        self._validate_terminal(record)
        self._atomic_write(
            self.terminal_path(record["task_id"]),
            record,
        )

        return record

    def retrieved_path(self, task_id):
        task_id = str(task_id)

        if not task_id or Path(task_id).name != task_id:
            raise GenerationJobRetrievedError(
                f"Invalid retrieved generation task identity: {task_id!r}"
            )

        return self.retrieved_dir / f"{task_id}.json"

    def retrieved_exists(self, task_id):
        return self.retrieved_path(task_id).is_file()

    def load_retrieved(self, task_id):
        task_id = str(task_id)
        path = self.retrieved_path(task_id)

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise GenerationJobRepositoryError(
                f"Cannot read retrieved generation job record: {path}"
            ) from exc

        try:
            record = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise GenerationJobRetrievedError(
                f"Corrupt retrieved generation job record: {path}"
            ) from exc

        self._validate_retrieved(record)

        if record["task_id"] != task_id:
            raise GenerationJobRetrievedError(
                "Retrieved generation job record task identity mismatch"
            )

        return record

    def persist_retrieved(self, record):
        self._validate_retrieved(record)
        self._atomic_write(
            self.retrieved_path(record["task_id"]),
            record,
        )

        return record

    def _validate(self, receipt):
        if not isinstance(receipt, dict):
            raise GenerationJobReceiptError(
                "Generation job receipt must be a dictionary"
            )

        if set(receipt) != self.RECEIPT_KEYS:
            raise GenerationJobReceiptError(
                "Generation job receipt fields do not match format version 1"
            )

        if receipt.get("format_version") != self.FORMAT_VERSION:
            raise GenerationJobReceiptError(
                "Unsupported generation job receipt format version"
            )

        if receipt.get("status") != "submitted":
            raise GenerationJobReceiptError(
                "Generation job receipt status must be 'submitted'"
            )

        for field in (
            "task_id",
            "task_type",
            "job_id",
            "provider",
            "submitted_at",
        ):
            value = receipt.get(field)
            if not isinstance(value, str) or not value:
                raise GenerationJobReceiptError(
                    f"Generation job receipt field {field!r} must be a non-empty string"
                )

        metadata = receipt.get("metadata")
        if (
            not isinstance(metadata, dict)
            or set(metadata) != self.METADATA_KEYS
        ):
            raise GenerationJobReceiptError(
                "Generation job receipt metadata must contain only scene_id and shot_id"
            )

    def _validate_terminal(self, record):
        if not isinstance(record, dict):
            raise GenerationJobTerminalError(
                "Terminal generation job record must be a dictionary"
            )

        expected_keys = self.TERMINAL_KEYS
        if record.get("status") == "succeeded":
            expected_keys = self.SUCCEEDED_TERMINAL_KEYS

        if set(record) != expected_keys:
            raise GenerationJobTerminalError(
                "Terminal generation job record fields do not match format version 1"
            )

        if record.get("format_version") != self.FORMAT_VERSION:
            raise GenerationJobTerminalError(
                "Unsupported terminal generation job record format version"
            )

        if record.get("status") not in self.TERMINAL_STATUSES:
            raise GenerationJobTerminalError(
                "Terminal generation job record status is not recognized"
            )

        for field in (
            "task_id",
            "task_type",
            "job_id",
            "provider",
            "terminal_at",
        ):
            value = record.get(field)
            if not isinstance(value, str) or not value:
                raise GenerationJobTerminalError(
                    "Terminal generation job record field "
                    f"{field!r} must be a non-empty string"
                )

        metadata = record.get("metadata")
        if (
            not isinstance(metadata, dict)
            or set(metadata) != self.METADATA_KEYS
        ):
            raise GenerationJobTerminalError(
                "Terminal generation job record metadata must contain only "
                "scene_id and shot_id"
            )

        if record["status"] == "succeeded" and (
            record.get("result_state") != "pending_retrieval"
            or record.get("asset_ready") is not False
        ):
            raise GenerationJobTerminalError(
                "Succeeded generation job must remain pending retrieval "
                "without a ready asset"
            )

    def _validate_retrieved(self, record):
        if not isinstance(record, dict):
            raise GenerationJobRetrievedError(
                "Retrieved generation job record must be a dictionary"
            )

        if set(record) != self.RETRIEVED_KEYS:
            raise GenerationJobRetrievedError(
                "Retrieved generation job record fields do not match "
                "format version 1"
            )

        if record.get("format_version") != self.FORMAT_VERSION:
            raise GenerationJobRetrievedError(
                "Unsupported retrieved generation job record format version"
            )

        for field in (
            "task_id",
            "task_type",
            "job_id",
            "provider",
            "retrieved_at",
        ):
            value = record.get(field)
            if not isinstance(value, str) or not value:
                raise GenerationJobRetrievedError(
                    "Retrieved generation job record field "
                    f"{field!r} must be a non-empty string"
                )

        metadata = record.get("metadata")
        if (
            not isinstance(metadata, dict)
            or set(metadata) != self.METADATA_KEYS
        ):
            raise GenerationJobRetrievedError(
                "Retrieved generation job record metadata must contain only "
                "scene_id and shot_id"
            )

        if record.get("result_state") != "retrieved":
            raise GenerationJobRetrievedError(
                "Retrieved generation job result_state must be 'retrieved'"
            )

        if record.get("asset_ready") is not False:
            raise GenerationJobRetrievedError(
                "Retrieved generation job must not expose a ready asset"
            )

        provider_result = record.get("provider_result")
        if not isinstance(provider_result, dict) or not provider_result:
            raise GenerationJobRetrievedError(
                "Retrieved provider_result must be a non-empty dictionary"
            )

        try:
            json.dumps(
                provider_result,
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise GenerationJobRetrievedError(
                "Retrieved provider_result must be JSON serializable"
            ) from exc

    def _atomic_write(self, target, receipt):
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    receipt,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temporary_path, target)
        except (OSError, TypeError, ValueError) as exc:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass

            raise GenerationJobPersistenceError(
                f"Cannot persist generation job receipt: {target}"
            ) from exc
