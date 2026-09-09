from collections.abc import Mapping
import json
from pathlib import Path

from core.ai_core.generation_job_repository import (
    GenerationJobRepository,
    GenerationJobRepositoryError,
)
from core.movie_engine.generation_lifecycle_coordinator import (
    GenerationLifecycleCoordinator,
    GenerationLifecycleCoordinatorError,
)


class GenerationSceneLifecycleError(RuntimeError):
    """Raised when a scene cannot advance through a safe bounded pass."""


ACTIVE_STATUSES = {
    "waiting",
    "processing",
    "submitted",
    "running",
    "succeeded",
}
TERMINAL_LOCAL_STATUSES = {
    "done",
    "failed",
    "cancelled",
}
TERMINAL_PROVIDER_STATUSES = {
    "succeeded",
    "failed",
    "cancelled",
}
IDENTITY_FIELDS = (
    "task_id",
    "task_type",
    "job_id",
    "provider",
    "metadata",
)


class GenerationSceneLifecycle:
    """Advance every active task in one scene by one Stage 2N step."""

    def __init__(
        self,
        project_path,
        provider_resolver,
        job_repository=None,
        audit=None,
        events=None,
    ):
        self.project_path = Path(project_path)
        self.provider_resolver = provider_resolver
        self.job_repository = (
            job_repository
            if job_repository is not None
            else GenerationJobRepository(project_path)
        )
        self.audit = audit
        self.events = events

    def advance_once(self, scene_id):
        dispatch_plan = self._preflight_scene(scene_id)

        if not dispatch_plan:
            return {
                "scene_id": scene_id,
                "advanced": [],
                "advanced_count": 0,
            }

        coordinator = GenerationLifecycleCoordinator(
            self.job_repository,
            self.provider_resolver,
            audit=self.audit,
            events=self.events,
        )
        advanced = []
        for task_id, _planned_action in dispatch_plan:
            try:
                result = coordinator.advance_once(task_id)
            except GenerationLifecycleCoordinatorError as exc:
                raise GenerationSceneLifecycleError(
                    "Generation scene lifecycle dispatch failed for task "
                    f"{task_id!r}: {exc}"
                ) from exc
            advanced.append(result)

        return {
            "scene_id": scene_id,
            "advanced": advanced,
            "advanced_count": len(advanced),
        }

    def inspect(self, scene_id):
        dispatch_plan = self._preflight_scene(scene_id)
        plan = [
            {
                "task_id": task_id,
                "action": action,
            }
            for task_id, action in dispatch_plan
        ]
        return {
            "scene_id": scene_id,
            "active_count": len(plan),
            "needs_advance": bool(plan),
            "plan": plan,
        }

    def _preflight_scene(self, scene_id):
        self._validate_scene_id(scene_id)
        document = self._load_scene_document(scene_id)
        active_tasks = self._validate_scene_document(document, scene_id)
        return tuple(
            self._preflight_active_task(task, scene_id)
            for task in active_tasks
        )

    def _validate_scene_id(self, scene_id):
        if (
            isinstance(scene_id, bool)
            or not isinstance(scene_id, int)
            or scene_id <= 0
        ):
            raise GenerationSceneLifecycleError(
                f"Generation scene identity is invalid: {scene_id!r}"
            )

    def _scene_path(self, scene_id):
        return (
            self.project_path
            / "render_output"
            / f"scene_{scene_id:03d}"
            / "generation_result.json"
        )

    def _load_scene_document(self, scene_id):
        path = self._scene_path(scene_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise GenerationSceneLifecycleError(
                f"Cannot read generation scene result: {path}"
            ) from exc

        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GenerationSceneLifecycleError(
                f"Generation scene result is corrupt: {path}"
            ) from exc

        if not isinstance(document, dict):
            raise GenerationSceneLifecycleError(
                "Generation scene result must be a dictionary"
            )
        return document

    def _validate_scene_document(self, document, scene_id):
        if document.get("scene_id") != scene_id:
            raise GenerationSceneLifecycleError(
                "Generation scene result identity mismatch"
            )

        tasks = document.get("tasks")
        if not isinstance(tasks, list):
            raise GenerationSceneLifecycleError(
                "Generation scene tasks must be a list"
            )

        active_tasks = []
        seen_task_ids = set()
        for task in tasks:
            if not isinstance(task, dict):
                raise GenerationSceneLifecycleError(
                    "Generation scene task must be a dictionary"
                )

            task_id = task.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                raise GenerationSceneLifecycleError(
                    f"Generation scene task identity is invalid: {task_id!r}"
                )
            if task_id in seen_task_ids:
                raise GenerationSceneLifecycleError(
                    f"Generation scene task identity is duplicated: {task_id!r}"
                )
            seen_task_ids.add(task_id)

            status = task.get("status")
            if status not in ACTIVE_STATUSES | TERMINAL_LOCAL_STATUSES:
                raise GenerationSceneLifecycleError(
                    f"Generation scene task status is invalid: {status!r}"
                )
            if status in TERMINAL_LOCAL_STATUSES:
                continue

            self._validate_active_task_structure(task, scene_id)
            active_tasks.append(task)

        return active_tasks

    def _validate_active_task_structure(self, task, scene_id):
        task_type = task.get("type")
        if not isinstance(task_type, str) or not task_type:
            raise GenerationSceneLifecycleError(
                f"Generation scene task type is invalid: {task_type!r}"
            )

        provider = task.get("provider")
        if not isinstance(provider, str) or not provider:
            raise GenerationSceneLifecycleError(
                f"Generation scene task provider is invalid: {provider!r}"
            )

        metadata = task.get("metadata")
        if not isinstance(metadata, dict):
            raise GenerationSceneLifecycleError(
                "Generation scene task metadata must be a dictionary"
            )
        if metadata.get("scene_id") != scene_id:
            raise GenerationSceneLifecycleError(
                "Generation scene task metadata identity mismatch"
            )
        if "shot_id" not in metadata or metadata["shot_id"] is None:
            raise GenerationSceneLifecycleError(
                "Generation scene task shot identity is missing"
            )

        result = task.get("result")
        if result is not None and not isinstance(result, dict):
            raise GenerationSceneLifecycleError(
                "Generation scene task result must be a dictionary or null"
            )

    def _preflight_active_task(self, task, scene_id):
        task_id = task["task_id"]
        receipt = self._repository_call(
            self.job_repository.resume,
            task_id,
            "submitted generation receipt",
        )
        self._validate_receipt_binding(task, receipt, scene_id)

        terminal_exists = self._repository_call(
            self.job_repository.terminal_exists,
            task_id,
            "terminal generation topology",
        )
        terminal = None
        if terminal_exists:
            terminal = self._repository_call(
                self.job_repository.load_terminal,
                task_id,
                "terminal generation record",
            )
            self._validate_terminal(receipt, terminal, task_id)

        retrieved_exists = self._repository_call(
            self.job_repository.retrieved_exists,
            task_id,
            "retrieved generation topology",
        )
        finalized_exists = self._repository_call(
            self.job_repository.finalized_exists,
            task_id,
            "finalized generation topology",
        )

        planned_action = self._planned_action(
            terminal,
            bool(retrieved_exists),
            bool(finalized_exists),
        )
        return (task_id, planned_action)

    def _repository_call(self, operation, task_id, description):
        try:
            return operation(task_id)
        except GenerationJobRepositoryError as exc:
            raise GenerationSceneLifecycleError(
                f"Cannot inspect {description} for task {task_id!r}: {exc}"
            ) from exc

    def _validate_receipt_binding(self, task, receipt, scene_id):
        if not isinstance(receipt, Mapping):
            raise GenerationSceneLifecycleError(
                "Submitted generation receipt must be dictionary-like"
            )

        metadata = receipt.get("metadata")
        if not isinstance(metadata, Mapping):
            raise GenerationSceneLifecycleError(
                "Submitted generation receipt metadata must be dictionary-like"
            )

        task_metadata = task["metadata"]
        if (
            receipt.get("task_id") != task["task_id"]
            or receipt.get("task_type") != task["type"]
            or receipt.get("provider") != task["provider"]
            or metadata.get("scene_id") != scene_id
            or metadata.get("scene_id") != task_metadata["scene_id"]
            or metadata.get("shot_id") != task_metadata["shot_id"]
        ):
            raise GenerationSceneLifecycleError(
                "Scene task and submitted receipt identities do not match"
            )

        result = task.get("result")
        if isinstance(result, dict):
            if (
                "job_id" in result
                and result["job_id"] != receipt.get("job_id")
            ):
                raise GenerationSceneLifecycleError(
                    "Scene task result job identity mismatch"
                )
            if (
                "provider" in result
                and result["provider"] != receipt.get("provider")
            ):
                raise GenerationSceneLifecycleError(
                    "Scene task result provider identity mismatch"
                )

    def _validate_terminal(self, receipt, terminal, task_id):
        if not isinstance(terminal, Mapping):
            raise GenerationSceneLifecycleError(
                "Terminal generation record must be dictionary-like"
            )
        if terminal.get("task_id") != task_id:
            raise GenerationSceneLifecycleError(
                "Terminal generation task identity mismatch"
            )
        if any(
            receipt.get(field) != terminal.get(field)
            for field in IDENTITY_FIELDS
        ):
            raise GenerationSceneLifecycleError(
                "Submitted and terminal generation identities do not match"
            )
        status = terminal.get("status")
        if status not in TERMINAL_PROVIDER_STATUSES:
            raise GenerationSceneLifecycleError(
                f"Terminal generation status is invalid: {status!r}"
            )

    def _planned_action(self, terminal, retrieved_exists, finalized_exists):
        if terminal is None:
            if retrieved_exists or finalized_exists:
                raise GenerationSceneLifecycleError(
                    "Generation lifecycle topology is invalid: later state "
                    "exists without terminal state"
                )
            return "poll"

        status = terminal["status"]
        if status in {"failed", "cancelled"}:
            if retrieved_exists or finalized_exists:
                raise GenerationSceneLifecycleError(
                    "Generation lifecycle topology is invalid: failed or "
                    "cancelled state contradicts later checkpoints"
                )
            return "reconcile_terminal"

        if finalized_exists and not retrieved_exists:
            raise GenerationSceneLifecycleError(
                "Generation lifecycle topology is invalid: finalized success "
                "state requires retrieved state"
            )
        if not retrieved_exists:
            return "retrieve"
        if not finalized_exists:
            return "finalize"
        return "reconcile_success"
