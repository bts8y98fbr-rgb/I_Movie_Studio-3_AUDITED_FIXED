from pathlib import Path
import json


class ProjectSerializer:


    def __init__(self, project_path):

        self.project_path = Path(project_path)

        self.project_path.mkdir(
            parents=True,
            exist_ok=True
        )


    def save(
        self,
        movie_data
    ):

        target = (
            self.project_path /
            "movie_project.json"
        )


        target.write_text(
            json.dumps(
                movie_data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )


        return target



    def load(self):

        target = (
            self.project_path /
            "movie_project.json"
        )


        if not target.exists():
            return None


        return json.loads(
            target.read_text(
                encoding="utf-8"
            )
        )
