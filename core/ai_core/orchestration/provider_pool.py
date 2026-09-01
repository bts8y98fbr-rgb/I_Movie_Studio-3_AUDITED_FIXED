from typing import List

from core.ai_core.providers.capabilities.provider_capability import (
    ProviderCapability,
)
from core.ai_core.providers.capabilities.capability_matcher import (
    CapabilityMatcher,
)
from core.ai_core.providers.provider_registry import ProviderRegistry


class ProviderPool:
    """
    Dynamic AI provider pool.

    Responsibilities:
    - register AI providers
    - connect with ProviderRegistry
    - store provider capabilities
    - select best provider
    - support parallel execution
    """

    def __init__(
        self,
        providers=None,
        registry: ProviderRegistry = None,
    ):
        self.registry = registry

        if registry:
            self.providers = registry.list_providers()
        else:
            self.providers = providers or []

        self.capabilities: List[ProviderCapability] = []

        self.matcher = CapabilityMatcher(
            self.capabilities
        )

        self._load_capabilities()

    def _sync_from_registry(self):
        """Synchronize the pool with its registry."""
        if self.registry is None:
            return

        self.providers = self.registry.list_providers()
        self.capabilities.clear()
        self._load_capabilities()

    def attach_registry(
        self,
        registry: ProviderRegistry,
    ):
        self.registry = registry
        self._sync_from_registry()

    def add_provider(
        self,
        provider,
        capability=None,
    ):
        if self.registry:
            self.registry.register(provider)
            self._sync_from_registry()
        else:
            self.providers.append(provider)

        if capability and capability not in self.capabilities:
            self.capabilities.append(capability)

    def _load_capabilities(self):
        for provider in self.providers:
            provider_capability = getattr(
                provider,
                "provider_capability",
                None,
            )

            if provider_capability:
                self.capabilities.append(
                    provider_capability
                )
                continue

            legacy = getattr(
                provider,
                "capabilities",
                None,
            )

            if callable(legacy):
                data = legacy()

                capability = ProviderCapability(
                    provider_name=provider.name,
                    media_type=data.get(
                        "media_type",
                        "video",
                    ),
                    supported_qualities=data.get(
                        "qualities",
                        [],
                    ),
                    max_duration_seconds=data.get(
                        "max_duration_seconds",
                        0,
                    ),
                    supports_hdr=data.get(
                        "supports_hdr",
                        False,
                    ),
                    max_parallel_jobs=data.get(
                        "max_parallel_jobs",
                        1,
                    ),
                    speed_score=data.get(
                        "speed_score",
                        50,
                    ),
                    quality_score=data.get(
                        "quality_score",
                        50,
                    ),
                    reliability_score=data.get(
                        "reliability_score",
                        50,
                    ),
                )

                self.capabilities.append(capability)

    def select(
        self,
        media_type="video",
        quality=None,
        duration=0,
        hdr=False,
        style=None,
    ):
        self._sync_from_registry()

        if self.capabilities:
            selected = self.matcher.find_best(
                media_type=media_type,
                quality=quality,
                duration=duration,
                hdr=hdr,
                style=style,
            )

            if selected:
                for provider in self.providers:
                    if provider.name == selected.provider_name:
                        return provider

        available = [
            provider
            for provider in self.providers
            if hasattr(provider, "name")
        ]

        if not available:
            return {
                "status": "fallback",
                "provider": None,
                "fallback_applied": True,
                "reason": "No AI providers available",
            }

        return available[0]

    def select_many(
        self,
        count=10,
        media_type="video",
        quality=None,
    ):
        self._sync_from_registry()
        return self.providers[:count]

    def status(self):
        self._sync_from_registry()
        return {
            "providers": [
                provider.name
                for provider in self.providers
            ],
            "count": len(self.providers),
            "capabilities": len(self.capabilities),
            "registry_connected": self.registry is not None,
            "parallel_ready": len(self.providers) >= 10,
        }
