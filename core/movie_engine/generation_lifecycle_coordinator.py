from collections.abc import Mapping

from core.ai_core.generation_job_asset_lifecycle import (
    GenerationJobAssetLifecycle,
    GenerationJobAssetLifecycleError,
)
from core.ai_core.generation_job_lifecycle import (
    GenerationJobLifecycle,
    GenerationJobLifecycleError,
)
from core.ai_core.generation_job_repository import (
    GenerationJobRepositoryError,
)
from core.ai_core.generation_job_result_lifecycle import (
    GenerationJobResultLifecycle,
    GenerationJobResultLifecycleError,
)
from core.movie_engine.generation_result_reconciler import (
    GenerationResultReconciler,
    GenerationResultReconciliationError,
)
from core.movie_engine.generation_terminal_reconciler import (
    GenerationTerminalReconciler,
    GenerationTerminalReconciliationError,
)


class GenerationLifecycleCoordinatorError(RuntimeError):
    """Raised when durable generation topology cannot advance safely."""


KNOWN_ORCHESTRATION_ERRORS = (
    GenerationJobRepositoryError,
    GenerationJobLifecycleError,
    GenerationJobResultLifecycleError,
    GenerationJobAssetLifecycleError,
    GenerationResultReconciliationError,
    GenerationTerminalReconciliationError,
)


class GenerationLifecycleCoordinator:
    """Dispatch exactly one lifecycle action from current durable state."""

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

    def advance_once(self, task_id):
        requested_task_id = str(task_id)
        submitted = self._repository_call(
            self.job_repository.resume,
            requested_task_id,
            "submitted generation receipt",
        )
        self._validate_requested_identity(
            submitted,
            requested_task_id,
            "Submitted",
        )

        terminal_exists = self._repository_call(
            self.job_repository.terminal_exists,
            requested_task_id,
            "terminal generation record topology",
        )
        terminal = None
        if terminal_exists:
            terminal = self._repository_call(
                self.job_repository.load_terminal,
                requested_task_id,
                "terminal generation record",
            )
            self._validate_requested_identity(
                terminal,
                requested_task_id,
                "Terminal",
            )
            self._validate_cross_record_identity(
                submitted,
                terminal,
            )
            self._validate_terminal_status(terminal)

        retrieved_exists = self._repository_call(
            self.job_repository.retrieved_exists,
            requested_task_id,
            "retrieved generation record topology",
        )
        finalized_exists = self._repository_call(
            self.job_repository.finalized_exists,
            requested_task_id,
            "finalized generation record topology",
        )

        if terminal is None:
            if retrieved_exists or finalized_exists:
                raise GenerationLifecycleCoordinatorError(
                    "Generation lifecycle topology is invalid: "
                    "retrieved or finalized state exists without terminal state"
                )
            child = GenerationJobLifecycle(
                self.job_repository,
                self.provider_resolver,
                audit=self.audit,
                events=self.events,
            )
            return self._dispatch(
                requested_task_id,
                "poll",
                child.poll_once,
            )

        status = terminal["status"]
        if status == "failed" or status == "cancelled":
            if retrieved_exists or finalized_exists:
                raise GenerationLifecycleCoordinatorError(
                    "Generation lifecycle topology is invalid: "
                    "failed or cancelled state contradicts later checkpoints"
                )
            child = GenerationTerminalReconciler(
                self.job_repository,
                audit=self.audit,
                events=self.events,
            )
            return self._dispatch(
                requested_task_id,
                "reconcile_terminal",
                child.reconcile_once,
            )

        if finalized_exists and not retrieved_exists:
            raise GenerationLifecycleCoordinatorError(
                "Generation lifecycle topology is invalid: "
                "finalized success state requires retrieved state"
            )

        if not retrieved_exists:
            child = GenerationJobResultLifecycle(
                self.job_repository,
                self.provider_resolver,
                audit=self.audit,
                events=self.events,
            )
            return self._dispatch(
                requested_task_id,
                "retrieve",
                child.retrieve_once,
            )

        if not finalized_exists:
            child = GenerationJobAssetLifecycle(
                self.job_repository,
                audit=self.audit,
                events=self.events,
            )
            return self._dispatch(
                requested_task_id,
                "finalize",
                child.finalize_once,
            )

        child = GenerationResultReconciler(
            self.job_repository,
            audit=self.audit,
            events=self.events,
        )
        return self._dispatch(
            requested_task_id,
            "reconcile_success",
            child.reconcile_once,
        )

    def _repository_call(
        self,
        operation,
        task_id,
        description,
    ):
        try:
            return operation(task_id)
        except GenerationJobRepositoryError as exc:
            raise GenerationLifecycleCoordinatorError(
                f"Cannot inspect {description}: {exc}"
            ) from exc

    def _validate_requested_identity(
        self,
        record,
        requested_task_id,
        label,
    ):
        if not isinstance(record, Mapping):
            raise GenerationLifecycleCoordinatorError(
                f"{label} generation record must be dictionary-like"
            )
        if record.get("task_id") != requested_task_id:
            raise GenerationLifecycleCoordinatorError(
                f"{label} generation task identity mismatch"
            )

    def _validate_cross_record_identity(
        self,
        submitted,
        terminal,
    ):
        submitted_identity = (
            submitted.get("task_id"),
            submitted.get("task_type"),
            submitted.get("job_id"),
            submitted.get("provider"),
            submitted.get("metadata"),
        )
        terminal_identity = (
            terminal.get("task_id"),
            terminal.get("task_type"),
            terminal.get("job_id"),
            terminal.get("provider"),
            terminal.get("metadata"),
        )
        if submitted_identity != terminal_identity:
            raise GenerationLifecycleCoordinatorError(
                "Submitted and terminal generation identities do not match"
            )

    def _validate_terminal_status(self, terminal):
        status = terminal.get("status")
        if status not in {
            "succeeded",
            "failed",
            "cancelled",
        }:
            raise GenerationLifecycleCoordinatorError(
                "Terminal generation status is invalid: "
                f"{status!r}"
            )

    def _dispatch(
        self,
        task_id,
        action,
        operation,
    ):
        try:
            result = operation(task_id)
        except KNOWN_ORCHESTRATION_ERRORS as exc:
            raise GenerationLifecycleCoordinatorError(
                "Generation lifecycle action failed: "
                f"{action}"
            ) from exc

        return {
            "task_id": task_id,
            "action": action,
            "result": result,
        }
