from datetime import datetime


class AssetVersionManager:

    def __init__(
        self,
        registry
    ):

        self.registry = registry



    def activate_version(
        self,
        asset_id,
        version
    ):

        versions = self.registry.get_versions(
            asset_id
        )

        if version not in versions:

            return False


        assets = self.registry._load()


        updated = False


        for asset in assets:

            if asset.get(
                "asset_id"
            ) == asset_id:

                asset["active_version"] = version

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



    def get_active_version(
        self,
        asset_id
    ):

        asset = self.registry.get_asset(
            asset_id
        )


        if not asset:

            return None


        return asset.get(
            "active_version"
        )



    def rollback(
        self,
        asset_id
    ):

        versions = self.registry.get_versions(
            asset_id
        )


        if len(versions) < 2:

            return False


        previous = versions[-2]


        return self.activate_version(
            asset_id,
            previous
        )



    def promote_latest(
        self,
        asset_id
    ):

        latest = self.registry.get_latest_version(
            asset_id
        )


        if not latest:

            return False


        return self.activate_version(
            asset_id,
            latest
        )
