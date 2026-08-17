from datetime import datetime
import json
from pathlib import Path
from queue import Queue
import uuid

from core.ai_core.ai_audit_log import AIAuditLog
from core.ai_core.result_storage import AIResultStorage


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
        self.metadata = dict(
            metadata or {}
        )

        self.status = "waiting"
        self.result = None
        self.output = None



class GenerationQueue:


    def __init__(self):

        self.queue = Queue()
        self.tasks = []



    def add_task(
        self,
        task
    ):

        self.queue.put(
            task
        )

        self.tasks.append(
            task
        )

        return task



    def _audit(
        self,
        task
    ):

        if not task.project_path:

            return None


        return AIAuditLog(
            task.project_path
        )



    def process_next(
        self
    ):

        if self.queue.empty():

            return None


        task = self.queue.get()

        task.status = "processing"


        audit = self._audit(
            task
        )


        try:

            selected_model = task.metadata.get(
                "shot_model_selection",
                {},
            )


            if audit:

                audit.record(
                    "model_selection",
                    {
                        "scene_id":
                            task.metadata.get(
                                "scene_id"
                            ),

                        "shot_id":
                            task.metadata.get(
                                "shot_id"
                            ),

                        "model":
                            selected_model.get(
                                "selected_model",
                                {},
                            ),

                        "provider":
                            task.provider.name,

                        "quality":
                            task.quality,
                    }
                )



            task.result = task.provider.generate(
                task.prompt,
                quality=task.quality,
                model=selected_model,
                project_path=task.project_path,
                metadata=task.metadata,
            )


            task.status = "done"



            if audit:

                audit.record(
                    "generation_complete",
                    {
                        "scene_id":
                            task.metadata.get(
                                "scene_id"
                            ),

                        "shot_id":
                            task.metadata.get(
                                "shot_id"
                            ),

                        "asset_id":
                            task.result.get(
                                "asset_id"
                            )
                            if isinstance(
                                task.result,
                                dict
                            )
                            else None,

                        "status":
                            task.status,
                    }
                )



        except Exception as exc:

            task.status = "failed"

            task.result = {
                "type":
                    task.task_type,

                "status":
                    "failed",

                "error":
                    str(exc),
            }


            if audit:

                audit.record(
                    "generation_failed",
                    {
                        "scene_id":
                            task.metadata.get(
                                "scene_id"
                            ),

                        "shot_id":
                            task.metadata.get(
                                "shot_id"
                            ),

                        "error":
                            str(exc),
                    }
                )



        self.save_result(
            task
        )


        return task



    def save_result(
        self,
        task
    ):

        if not task.project_path:

            return None


        storage = AIResultStorage(
            task.project_path
        )


        target = storage.save_result(
            task
        )


        task.output = str(
            target
        )


        return target



    def process_all(
        self
    ):

        results = []


        while not self.queue.empty():

            results.append(
                self.process_next()
            )


        return results



    def get_status(
        self
    ):

        return [

            {
                "task_id":
                    task.task_id,

                "type":
                    task.task_type,

                "prompt":
                    task.prompt,

                "provider":
                    task.provider.name,

                "quality":
                    task.quality,

                "status":
                    task.status,

                "result":
                    task.result,

                "output":
                    task.output,

                "metadata":
                    task.metadata,
            }

            for task in self.tasks

        ]
