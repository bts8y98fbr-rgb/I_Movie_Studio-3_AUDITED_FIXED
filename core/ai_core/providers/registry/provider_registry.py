from typing import Dict, List


class ProviderRegistry:
    """
    Central registry for AI providers.

    Stores available providers and exposes
    them to orchestration layers.
    """

    def __init__(self):
        self.providers: Dict[str, object] = {}


    def register(
        self,
        provider,
    ):

        if not hasattr(provider, "name"):
            raise ValueError(
                "Provider must have name"
            )

        self.providers[provider.name] = provider


    def unregister(
        self,
        provider_name,
    ):

        self.providers.pop(
            provider_name,
            None,
        )


    def get(
        self,
        provider_name,
    ):

        return self.providers.get(
            provider_name
        )


    def all(self) -> List[object]:

        return list(
            self.providers.values()
        )


    def count(self) -> int:

        return len(
            self.providers
        )


    def status(self):

        return {
            "providers": list(
                self.providers.keys()
            ),
            "count": self.count(),
        }
