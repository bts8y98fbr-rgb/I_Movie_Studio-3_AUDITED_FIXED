from datetime import datetime


class ProjectReport:

    def __init__(
        self,
        registry,
        generation_reports=None,
    ):

        self.registry = registry
        self.generation_reports = (
            generation_reports
        )



    def build(
        self
    ):

        assets = self.registry.list_assets()


        report = {

            "created":
                datetime.now().isoformat(),

            "total_assets":
                len(assets),

            "assets":
                assets,

            "types":
                {},

            "providers":
                {},

            "models":
                {},

        }



        for asset in assets:

            asset_type = asset.get(
                "type"
            )

            provider = asset.get(
                "provider"
            )

            model = (
                asset.get(
                    "model",
                    {}
                )
                .get(
                    "name"
                )
            )



            if asset_type:

                report["types"][asset_type] = (
                    report["types"].get(
                        asset_type,
                        0
                    )
                    + 1
                )



            if provider:

                report["providers"][provider] = (
                    report["providers"].get(
                        provider,
                        0
                    )
                    + 1
                )



            if model:

                report["models"][model] = (
                    report["models"].get(
                        model,
                        0
                    )
                    + 1
                )



        return report
