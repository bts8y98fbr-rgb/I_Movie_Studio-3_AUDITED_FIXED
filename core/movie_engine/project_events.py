from datetime import datetime
from pathlib import Path
import json


class ProjectEvents:


    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )

        self.events_file = (
            self.project_path
            / "project_events.json"
        )

        self.events = []


        if self.events_file.exists():

            self.events = json.loads(
                self.events_file.read_text(
                    encoding="utf-8"
                )
            )



    def emit(
        self,
        event_type,
        data
    ):

        event = {

            "type":
                event_type,

            "timestamp":
                datetime.now().isoformat(),

            "data":
                data,

        }


        self.events.append(
            event
        )


        self._save()


        return event



    def _save(
        self
    ):

        self.events_file.write_text(
            json.dumps(
                self.events,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )



    def get_all(
        self
    ):

        return self.events



    def find(
        self,
        event_type
    ):

        return [

            event

            for event in self.events

            if event["type"] == event_type

        ]



    def latest(
        self
    ):

        if not self.events:

            return None


        return self.events[-1]
