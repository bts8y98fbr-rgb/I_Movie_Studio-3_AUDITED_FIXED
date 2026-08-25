import json
from datetime import datetime


class DashboardAPI:


    def __init__(
        self,
        dashboard
    ):

        self.dashboard = dashboard



    def get_project_status(
        self
    ):

        status = self.dashboard.get_status()


        return {

            "success":
                True,

            "timestamp":
                datetime.now().isoformat(),

            "data":
                status,

        }



    def export_json(
        self
    ):

        response = self.get_project_status()


        return json.dumps(
            response,
            indent=2,
            ensure_ascii=False,
        )
