from datetime import datetime


class GenerationReport:

    def __init__(
        self,
        registry,
        audit,
        lifecycle=None,
        version_manager=None,
    ):

        self.registry = registry
        self.audit = audit
        self.lifecycle = lifecycle
        self.version_manager = version_manager



    def build(
        self,
        asset_id
    ):

        asset = self.registry.get_asset(
            asset_id
        )


        if not asset:

            return None



        report = {

            "asset_id":
                asset_id,

            "created":
                datetime.now().isoformat(),

            "asset":
                asset,

            "active_version":
                None,

            "status":
                None,

            "audit_events":
                [],

        }



        if self.version_manager:

            report["active_version"] = (
                self.version_manager.get_active_version(
                    asset_id
                )
            )



        if self.lifecycle:

            report["status"] = (
                self.lifecycle.get_status(
                    asset_id
                )
            )



        report["audit_events"] = (
            self.audit.find_by_shot(
                asset.get(
                    "generation_context",
                    {}
                ).get(
                    "shot_id"
                )
            )
            if self.audit
            else []
        )



        return report
