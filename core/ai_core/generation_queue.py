from pathlib import Path
from queue import Queue
import uuid

from core.ai_core.ai_audit_log import AIAuditLog
from core.ai_core.result_storage import AIResultStorage
from core.movie_engine.project_events import ProjectEvents


class GenerationTask:
    def __init__(
        self,
        task_type,
        prompt,
        provider,
        quality="8k",
        project_path=None,
        metadata=None,
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

        self.status = "waiting"
        self.result = None
        self.output = None


class GenerationQueue:
    def __init__(self):
        self.queue = Queue()
        self.tasks = []

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
