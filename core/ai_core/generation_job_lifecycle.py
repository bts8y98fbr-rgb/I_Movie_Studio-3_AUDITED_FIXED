from collections.abc import Mapping
from datetime import datetime, timezone

from core.ai_core.generation_job_repository import (
    GenerationJobRepositoryError,
)


class GenerationJobLifecycleError(RuntimeError):
    """Raised when one remote generation-job polling step is invalid."""


class GenerationJobLifecycle:
    RUNNING_STATUSES = {
        "processing": "running",
        "running": "running",
    }
    TERMINAL_STATUSES = {
        "succeeded",
        "failed",
        "cancelled",
    }

    def __init__(
        self,
        job_repository,
        provider_resolver,
        audit=None,
        events=None,
    ):
        self.job_repository = job_repository
        self.provider_resolver = provider_resolver
        self.audit = audit
        self.events = events

    def poll_once(self, task_id):
        existing_terminal = self._load_existing_terminal(task_id)
        if existing_terminal is not None:
            return existing_terminal

        receipt = self._load_submitted_receipt(task_id)
        if receipt["task_id"] != str(task_id):
            raise GenerationJobLifecycleError(
                "Generation task identity mismatch: "
                f"requested={str(task_id)!r}, receipt={receipt['task_id']!r}"
            )

        provider_name = receipt["provider"]
        job_id = receipt["job_id"]
        provider = self.provider_resolver.get(provider_name)

        if provider is None:
            raise GenerationJobLifecycleError(
                f"Generation provider {provider_name!r} is unavailable"
            )

        resolved_name = getattr(provider, "name", None)
        if resolved_name != provider_name:
            raise GenerationJobLifecycleError(
                "Generation provider identity mismatch: "
                f"receipt={provider_name!r}, resolved={resolved_name!r}"
            )

        get_status = getattr(provider, "get_status", None)
        if not callable(get_status):
            raise GenerationJobLifecycleError(
                f"Generation provider {provider_name!r} cannot report job status"
            )

        response = get_status(job_id)
        status = self._validate_response(response, provider_name, job_id)

        if status in self.RUNNING_STATUSES:
            return {
                "status": self.RUNNING_STATUSES[status],
                "job_id": job_id,
                "provider": provider_name,
            }

        terminal = {
            "format_version": self.job_repository.FORMAT_VERSION,
            "task_id": receipt["task_id"],
            "task_type": receipt["task_type"],
            "job_id": job_id,
            "provider": provider_name,
            "status": status,
            "metadata": dict(receipt["metadata"]),
            "terminal_at": datetime.now(timezone.utc).isoformat(),
        }

        if status == "succeeded":
            terminal.update(
                {
                    "result_state": "pending_retrieval",
                    "asset_ready": False,
                }
            )

        durable_terminal = self._persist_terminal(terminal)
        self._record_observability(durable_terminal)

        return durable_terminal

    def _load_existing_terminal(self, task_id):
        try:
            if not self.job_repository.terminal_exists(task_id):
                return None

            return self.job_repository.load_terminal(task_id)
        except GenerationJobRepositoryError as exc:
            raise GenerationJobLifecycleError(
                f"Cannot load terminal generation job outcome: {exc}"
            ) from exc

    def _load_submitted_receipt(self, task_id):
        try:
            return self.job_repository.resume(task_id)
        except GenerationJobRepositoryError as exc:
            raise GenerationJobLifecycleError(
                f"Invalid submitted generation job receipt: {exc}"
            ) from exc

    def _persist_terminal(self, terminal):
        try:
            return self.job_repository.persist_terminal(terminal)
        except GenerationJobRepositoryError as exc:
            raise GenerationJobLifecycleError(
                f"Cannot persist terminal generation job outcome: {exc}"
            ) from exc

    def _validate_response(self, response, provider_name, job_id):
        if not isinstance(response, Mapping):
            raise GenerationJobLifecycleError(
                "Generation provider status response must be dictionary-like"
            )

        response_status = response.get("status")

        if not isinstance(response_status, str) or not response_status:
            raise GenerationJobLifecycleError(
                "Generation provider status is missing or unknown: "
                f"{response_status!r}"
            )

        recognized_statuses = set(self.RUNNING_STATUSES) | self.TERMINAL_STATUSES

        if response_status not in recognized_statuses:
            raise GenerationJobLifecycleError(
                f"Generation provider status is missing or unknown: {response_status!r}"
            )

        if "job_id" in response and response["job_id"] != job_id:
            raise GenerationJobLifecycleError(
                "Generation job identity mismatch: "
                f"receipt={job_id!r}, response={response['job_id']!r}"
            )

        if "provider" in response and response["provider"] != provider_name:
            raise GenerationJobLifecycleError(
                "Generation provider identity mismatch: "
                f"receipt={provider_name!r}, response={response['provider']!r}"
            )

        return response_status

    def _record_observability(self, terminal):
        if self.audit is not None:
            try:
                self.audit.record(
                    "generation_job_terminal",
                    dict(terminal),
                )
            except Exception:
                pass

        if self.events is not None:
            try:
                self.events.emit(
                    "generation_job_terminal",
                    dict(terminal),
                )
            except Exception:
                pass
