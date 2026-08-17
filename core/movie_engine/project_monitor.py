from datetime import datetime


class ProjectMonitor:


    def __init__(
        self,
        engine,
        dashboard=None,
    ):

        self.engine = engine
        self.dashboard = dashboard



    def get_generation_state(
        self
    ):

        state = {

            "timestamp":
                datetime.now().isoformat(),

            "queue":
                [],

            "tasks":
                [],

            "dashboard":
                None,

        }


        if hasattr(
            self.engine,
            "queue"
        ):

            state["queue"] = (
                self.engine.queue.get_status()
            )


            state["tasks"] = (
                len(
                    self.engine.queue.tasks
                )
            )



        if self.dashboard:

            state["dashboard"] = (
                self.dashboard.get_status()
            )


        return state



    def get_active_tasks(
        self
    ):

        tasks = []


        if hasattr(
            self.engine,
            "queue"
        ):

            for task in self.engine.queue.tasks:

                if task.status in (
                    "waiting",
                    "processing",
                ):

                    tasks.append(
                        {
                            "task_id":
                                task.task_id,

                            "type":
                                task.task_type,

                            "status":
                                task.status,

                        }
                    )


        return tasks
