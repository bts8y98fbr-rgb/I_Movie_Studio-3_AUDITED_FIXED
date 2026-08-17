from datetime import datetime
import json
from pathlib import Path
from queue import Queue
import uuid


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
        self.project_path = Path(project_path) if project_path else None
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


    def save_result(self, task):
        if not task.project_path:
            return None

        folder = (
            task.project_path
            / "media"
            / task.task_type
        )

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            f"{task.task_type}_{task.quality}_"
            f"{timestamp}_{task.task_id}.json"
        )

        target = folder / filename

        data = {
            "task_id": task.task_id,
            "type": task.task_type,
            "prompt": task.prompt,
            "provider": task.provider.name,
            "quality": task.quality,
            "status": task.status,
            "metadata": task.metadata,
            "result": task.result,
        }

        target.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        task.output = str(target)

        return target


    def process_next(self):

        if self.queue.empty():
            return None


        task = self.queue.get()

        task.status = "processing"


        try:

            selected_model = task.metadata.get(
                "shot_model_selection",
                {},
            )


            task.result = task.provider.generate(
                task.prompt,
                quality=task.quality,
                model=selected_model,
                project_path=task.project_path,
                metadata=task.metadata,
            )


            task.status = "done"


        except Exception as exc:

            task.status = "failed"

            task.result = {
                "type": task.task_type,
                "status": "failed",
                "error": str(exc),
            }


        self.save_result(task)

        return task



    def process_all(self):

        results = []

        while not self.queue.empty():

            results.append(
                self.process_next()
            )

        return results



    def get_status(self):

        return [

            {
                "task_id": task.task_id,
                "type": task.task_type,
                "prompt": task.prompt,
                "provider": task.provider.name,
                "quality": task.quality,
                "status": task.status,
                "result": task.result,
                "output": task.output,
                "metadata": task.metadata,
            }

            for task in self.tasks

        ]
