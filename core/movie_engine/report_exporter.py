import json
from datetime import datetime
from pathlib import Path


class ReportExporter:


    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )

        self.report_dir = (
            self.project_path
            / "reports"
        )

        self.report_dir.mkdir(
            parents=True,
            exist_ok=True,
        )



    def export_json(
        self,
        report,
        filename="project_report.json"
    ):

        target = (
            self.report_dir
            / filename
        )


        payload = {

            "exported":
                datetime.now().isoformat(),

            "report":
                report,

        }


        target.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


        return target



    def load_json(
        self,
        filename="project_report.json"
    ):

        target = (
            self.report_dir
            / filename
        )


        if not target.exists():

            return None


        return json.loads(
            target.read_text(
                encoding="utf-8"
            )
        )
