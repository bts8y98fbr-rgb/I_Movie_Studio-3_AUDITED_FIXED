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

    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.submitted_dir = (
            self.project_path
            / "generation_jobs"
            / "submitted"
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
