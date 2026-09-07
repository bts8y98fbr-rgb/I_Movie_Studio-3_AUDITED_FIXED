from pathlib import Path
from queue import Queue
import uuid

from core.ai_core.ai_audit_log import AIAuditLog
from core.ai_core.generation_job_repository import GenerationJobRepository
from core.ai_core.model_policy import ModelPolicy, SelectionMode
from core.ai_core.result_storage import AIResultStorage
from core.movie_engine.project_events import ProjectEvents


class GenerationTask:
    def __init__(
        self,
        task_type,
        prompt,
        provider,
        quality= "4k",
        project_path=None,
        metadata=None,
        model_policy=None,
    ):
        self.task_id = str(uuid.uuid4())[:8]
        self.task_type = task_type
        self.prompt = prompt
        self.provider = provider
        self.quality = quality

        self.project_path = (
            Path(project_path)
            if project_path
            else None
        )

        self.metadata = dict(metadata or {})
        self.model_policy = model_policy

        self.status = "waiting"
        self.result = None
        self.output = None


class GenerationQueue:
    def __init__(self, job_repository=None):
        self.queue = Queue()
        self.tasks = []
        self.job_repository = job_repository
        self._job_repository_injected = job_repository is not None

    def add_task(self, task):
        self.queue.put(task)
        self.tasks.append(task)
        return task

    def _audit(self, task):
        if not task.project_path:
            return None

        return AIAuditLog(task.project_path)

    def _events(self, task):
        if not task.project_path:
            return None

        return ProjectEvents(task.project_path)

    def _submitted_job_repository(self, task):
        if self._job_repository_injected:
            return self.job_repository

        if not task.project_path:
            return None

        self.job_repository = GenerationJobRepository(
            task.project_path
        )

        return self.job_repository

    def _record_submission_observability(
        self,
        audit,
        events,
        task,
        submission_data,
    ):
        if audit:
            try:
                audit.record(
                    "generation_submitted",
                    submission_data,
                )
            except Exception:
                pass

        if events:
            try:
                events.emit(
                    "generation_submitted",
                    {
                        "task_id": task.task_id,
                        **submission_data,
                    },
                )
            except Exception:
                pass

    def process_next(self):
        if self.queue.empty():
            return None

        task = self.queue.get()
        task.status = "processing"

        audit = self._audit(task)
        events = self._events(task)

        if events:
            events.emit(
                "generation_started",
                {
                    "task_id": task.task_id,
                    "scene_id": task.metadata.get("scene_id"),
                    "shot_id": task.metadata.get("shot_id"),
                },
            )

        try:
            shot_model_selection = task.metadata.get(
                "shot_model_selection",
                {},
            )

            selected_model = {}
            if isinstance(shot_model_selection, dict):
                selected_model = shot_model_selection.get(
                    "selected_model",
                    {},
                )

            model_policy = task.model_policy
            if (
                isinstance(model_policy, ModelPolicy)
                and model_policy.mode == SelectionMode.FIXED
            ):
                provider_name = getattr(task.provider, "name", None)
                selected_model_name = (
                    selected_model.get("name")
                    if isinstance(selected_model, dict)
                    else None
                )

                if (
                    not isinstance(provider_name, str)
                    or not isinstance(selected_model_name, str)
                    or not model_policy.allows(
                        provider_name,
                        selected_model_name,
                    )
                ):
                    raise RuntimeError(
                        "Fixed model policy mismatch: "
                        f"requested provider={model_policy.provider!r}, "
                        f"model={model_policy.model!r}; "
                        f"selected provider={provider_name!r}, "
                        f"model={selected_model_name!r}"
                    )

            if audit:
                audit.record(
                    "model_selection",
                    {
                        "scene_id": task.metadata.get("scene_id"),
                        "shot_id": task.metadata.get("shot_id"),
                        "model": selected_model,
                        "provider": task.provider.name,
                        "quality": task.quality,
                    },
                )

            task.result = task.provider.generate(
                task.prompt,
                quality=task.quality,
                model=shot_model_selection,
                project_path=task.project_path,
                metadata=task.metadata,
            )

            if (
                isinstance(task.result, dict)
                and task.result.get("status") == "submitted"
            ):
                task.status = "submitted"

                job_repository = self._submitted_job_repository(
                    task
                )

                if job_repository:
                    job_repository.persist(
                        task,
                        task.result,
                    )

                submission_data = {
                    "scene_id": task.metadata.get("scene_id"),
                    "shot_id": task.metadata.get("shot_id"),
                    "job_id": task.result.get("job_id"),
                    "provider": task.provider.name,
                }

                self._record_submission_observability(
                    audit,
                    events,
                    task,
                    submission_data,
                )

                return task

            if not isinstance(task.result, dict):
                task.result = {
                    "result": task.result,
                }

            task.result.setdefault(
                "model",
                selected_model,
            )

            result_metadata = task.result.setdefault(
                "metadata",
                {},
            )

            if isinstance(result_metadata, dict):
                result_metadata.setdefault(
                    "selected_model",
                    selected_model,
                )

            task.status = "done"

            asset_id = None

            if isinstance(task.result, dict):
                asset_id = task.result.get("asset_id")

            if audit:
                audit.record(
                    "generation_complete",
                    {
                        "scene_id": task.metadata.get("scene_id"),
                        "shot_id": task.metadata.get("shot_id"),
                        "asset_id": asset_id,
                        "status": task.status,
                    },
                )

            if events:
                events.emit(
                    "generation_completed",
                    {
                        "task_id": task.task_id,
                        "asset_id": asset_id,
                        "status": task.status,
                    },
                )

        except Exception as exc:
            task.status = "failed"

            task.result = {
                "type": task.task_type,
                "status": "failed",
                "error": str(exc),
            }

            if audit:
                audit.record(
                    "generation_failed",
                    {
                        "scene_id": task.metadata.get("scene_id"),
                        "shot_id": task.metadata.get("shot_id"),
                        "error": str(exc),
                    },
                )

            if events:
                events.emit(
                    "generation_failed",
                    {
                        "task_id": task.task_id,
                        "error": str(exc),
                    },
                )

        self.save_result(task)

        return task

    def process_all(self):
        results = []

        while not self.queue.empty():
            result = self.process_next()

            if result:
                results.append(result)

        return results

    def get_status(self):
        return [
            {
                "task_id": task.task_id,
                "type": task.task_type,
                "status": task.status,
                "metadata": task.metadata,
                "result": task.result,
                "provider": (
                    task.provider.name
                    if hasattr(task.provider, "name")
                    else None
                ),
                "quality": task.quality,
                "output": task.output,
            }
            for task in self.tasks
        ]

    def save_result(self, task):
        if not task.project_path:
            return None

        storage = AIResultStorage(task.project_path)

        target = storage.save_result(task)

        task.output = str(target)

        return target
