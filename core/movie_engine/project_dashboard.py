from datetime import datetime


class ProjectDashboard:


    def __init__(
        self,
        registry,
        audit=None,
        manifest=None,
    ):

        self.registry = registry
        self.audit = audit
        self.manifest = manifest



    def get_status(
        self
    ):

        assets = (
            self.registry.list_assets()
        )


        dashboard = {

            "generated":
                datetime.now().isoformat(),

            "project":
                {
                    "assets":
                        len(assets),
                },

            "providers":
                {},

            "models":
                {},

            "audit_events":
                0,

            "manifest":
                None,

        }



        for asset in assets:

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


            if provider:

                dashboard["providers"][provider] = (
                    dashboard["providers"].get(
                        provider,
                        0
                    )
                    + 1
                )


            if model:

                dashboard["models"][model] = (
                    dashboard["models"].get(
                        model,
                        0
                    )
                    + 1
                )



        if self.audit:

            dashboard["audit_events"] = len(
                self.audit.get_all()
            )



        if self.manifest:

            dashboard["manifest"] = (
                self.manifest.load()
            )



        return dashboard
