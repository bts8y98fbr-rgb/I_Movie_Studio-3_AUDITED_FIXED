from datetime import datetime
import json
from pathlib import Path


class AIAuditLog:

    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )

        self.audit_dir = (
            self.project_path
            / "audit"
        )

        self.audit_file = (
            self.audit_dir
            / "ai_audit.json"
        )

        self.audit_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.audit_file.exists():

            self.audit_file.write_text(
                json.dumps(
                    [],
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )



    def _load(self):

        return json.loads(
            self.audit_file.read_text(
                encoding="utf-8"
            )
        )



    def _save(
        self,
        entries
    ):

        self.audit_file.write_text(
            json.dumps(
                entries,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )



    def record(
        self,
        event,
        data
    ):

        entries = self._load()


        entry = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }


        entries.append(
            entry
        )


        self._save(
            entries
        )


        return entry



    def get_all(
        self
    ):

        return self._load()



    def find_by_shot(
        self,
        shot_id
    ):

        return [

            item
            for item in self._load()
            if item.get(
                "event"
            )
            ==
            "model_selection"
            and
            item.get(
                "data",
                {}
            ).get(
                "shot_id"
            )
            ==
            shot_id

        ]



    def find_by_model(
        self,
        model_name
    ):

        return [

            item
            for item in self._load()
            if item.get(
                "event"
            )
            ==
            "model_selection"
            and
            item.get(
                "data",
                {}
            )
            .get(
                "model",
                {}
            )
            .get(
                "name"
            )
            ==
            model_name

        ]
