from core.ai_core.providers import (
    ImageProvider,
    VideoProvider,
    VoiceProvider,
    MusicProvider,
)
from core.ai_core.providers.provider_registry import ProviderRegistry


class ProviderManager:

    def __init__(self, registry=None):
        self.registry = registry if registry is not None else ProviderRegistry()

    @property
    def providers(self):
        """Backward-compatible access to registered providers."""
        return self.registry.providers

    def register(self, provider):
        return self.registry.register(provider)

    def unregister(self, name):
        return self.registry.unregister(name)

    def load_default_providers(self):
        self.register(ImageProvider())
        self.register(VideoProvider())
        self.register(VoiceProvider())
        self.register(MusicProvider())

    def list_providers(self):
        return [
            provider.status()
            for provider in self.registry.list_providers()
        ]

    def get(self, name):
        return self.registry.get(name)
