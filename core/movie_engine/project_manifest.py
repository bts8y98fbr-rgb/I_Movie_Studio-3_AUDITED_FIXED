import json
from datetime import datetime
from pathlib import Path


class ProjectManifest:


    def __init__(
        self,
        project_path
    ):

        self.project_path = Path(
            project_path
        )

        self.manifest_file = (
            self.project_path
            / "project_manifest.json"
        )



    def build(
        self,
        project_report,
        assets=None,
        audit_summary=None,
    ):

        manifest = {

            "project_path":
                str(
                    self.project_path
                ),

            "created":
                datetime.now().isoformat(),

            "summary":
                project_report,

            "assets":
                assets or [],

            "audit":
                audit_summary or {},

        }


        return manifest



    def save(
        self,
        manifest
    ):

        self.manifest_file.write_text(
            json.dumps(
                manifest,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return self.manifest_file



    def load(
        self
    ):

        if not self.manifest_file.exists():

            return None


        return json.loads(
            self.manifest_file.read_text(
                encoding="utf-8"
            )
        )
