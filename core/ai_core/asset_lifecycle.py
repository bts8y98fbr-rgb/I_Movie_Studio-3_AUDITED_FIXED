from datetime import datetime


class AssetLifecycle:

    VALID_STATES = [
        "generated",
        "processing",
        "approved",
        "active",
        "archived",
        "failed",
    ]


    def __init__(
        self,
        registry
    ):

        self.registry = registry



    def set_status(
        self,
        asset_id,
        status
    ):

        if status not in self.VALID_STATES:

            raise ValueError(
                f"Invalid asset status: {status}"
            )


        assets = self.registry._load()


        updated = False


        for asset in assets:

            if asset.get(
                "asset_id"
            ) == asset_id:

                asset["status"] = status

                asset["updated"] = (
                    datetime.now().isoformat()
                )

                updated = True



        if not updated:

            return False



        self.registry._save(
            assets
        )


        return True



    def activate(
        self,
        asset_id
    ):

        return self.set_status(
            asset_id,
            "active"
        )



    def approve(
        self,
        asset_id
    ):

        return self.set_status(
            asset_id,
            "approved"
        )



    def archive(
        self,
        asset_id
    ):

        return self.set_status(
            asset_id,
            "archived"
        )



    def fail(
        self,
        asset_id
    ):

        return self.set_status(
            asset_id,
            "failed"
        )



    def get_status(
        self,
        asset_id
    ):

        asset = self.registry.get_asset(
            asset_id
        )


        if not asset:

            return None


        return asset.get(
            "status"
        )
