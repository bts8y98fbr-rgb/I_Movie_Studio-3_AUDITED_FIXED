from .base_provider import BaseAIProvider


class ProviderRegistry:

    def __init__(self):
        self.providers = {}

    def register(self, provider: BaseAIProvider):
        self.providers[provider.name] = provider

    def get(self, name):
        return self.providers.get(name)

    def list_providers(self):
        return list(self.providers.keys())


registry = ProviderRegistry()
