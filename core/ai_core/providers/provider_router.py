from .provider_catalog import ProviderCatalog


class ProviderRouter:
    """Select the best eligible provider for a task."""

    def __init__(self, catalog=None, execution_available=None):
        self.catalog = catalog or ProviderCatalog()
        self.execution_available = execution_available

    def select(
        self,
        media_type: str,
        mode: str = "mixed",
        commercial: bool = False,
    ):
        candidates = [
            provider
            for provider in self.catalog.list()
            if provider.status == "active"
            and provider.supports(media_type)
            and provider.api_available
            and (
                self.execution_available is None
                or self.execution_available(provider.name)
            )
        ]

        if commercial:
            candidates = [
                provider
                for provider in candidates
                if provider.commercial_use is not False
            ]

        if mode == "free":
            candidates = [
                provider
                for provider in candidates
                if provider.free_api or provider.free_credits
            ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda provider: (
                provider.quality_score + provider.speed_score
            ),
        )
