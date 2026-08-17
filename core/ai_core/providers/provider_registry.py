from .base_provider import BaseAIProvider


class ProviderRegistry:

    def __init__(self):
        self.providers = {}

    def register(self, provider: BaseAIProvider):
        if not isinstance(provider, BaseAIProvider):
            raise TypeError("provider must inherit from BaseAIProvider")

        self.providers[provider.name] = provider
        return provider

    def unregister(self, name):
        return self.providers.pop(name, None)

    def get(self, name):
        return self.providers.get(name)

    def list_providers(self):
        return list(self.providers.values())

    def list_names(self):
        return list(self.providers.keys())

    def clear(self):
        self.providers.clear()


registry = ProviderRegistry()
