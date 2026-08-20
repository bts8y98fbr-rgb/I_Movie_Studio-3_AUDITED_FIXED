from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class ProviderCapability:
    name: str
    media_type: str
    qualities: List[str] = field(default_factory=list)
    max_parallel_jobs: int = 1
    priority: int = 0


class ProviderPool:
    """
    Dynamic AI provider pool.

    Manages multiple external AI providers.

    Providers are selected by:
        - media type
        - quality requirements
        - priority
        - available capacity
    """

    def __init__(
        self,
        providers=None,
    ):
        self.providers = providers or []
        self.capabilities = []

        self._load_capabilities()


    def add_provider(
        self,
        provider,
        capability=None,
    ):
        self.providers.append(provider)

        if capability:
            self.capabilities.append(
                capability
            )


    def _load_capabilities(self):

        for provider in self.providers:

            capability = getattr(
                provider,
                "capabilities",
                None,
            )

            if callable(capability):

                data = capability()

                self.capabilities.append(
                    ProviderCapability(
                        name=provider.name,
                        media_type=data.get(
                            "media_types",
                            ["unknown"]
                        )[0],
                        qualities=data.get(
                            "qualities",
                            []
                        ),
                        max_parallel_jobs=data.get(
                            "max_parallel_jobs",
                            1,
                        ),
                        priority=data.get(
                            "priority",
                            0,
                        ),
                    )
                )


    def select(
        self,
        media_type="video",
        quality=None,
    ):

        candidates = []

        for provider in self.providers:

            if not hasattr(
                provider,
                "name",
            ):
                continue

            candidates.append(
                provider
            )


        if not candidates:

            raise RuntimeError(
                "No providers available"
            )


        return sorted(
            candidates,
            key=lambda item:
                item.name
        )[0]


    def select_many(
        self,
        count=10,
        media_type="video",
        quality=None,
    ):

        providers = self.providers[:]

        if len(providers) <= count:

            return providers


        return providers[:count]


    def status(self):

        return {

            "providers": [
                provider.name
                for provider in self.providers
            ],

            "count":
                len(self.providers),

            "parallel_ready":
                len(self.providers) >= 10,

        }
