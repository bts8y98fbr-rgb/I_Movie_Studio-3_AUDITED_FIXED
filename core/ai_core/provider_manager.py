from core.ai_core.providers import (
    ImageProvider,
    VideoProvider,
    VoiceProvider,
    MusicProvider
)


class ProviderManager:

    def __init__(self):

        self.providers = {}


    def register(self, provider):

        self.providers[provider.name] = provider


    def load_default_providers(self):

        self.register(ImageProvider())
        self.register(VideoProvider())
        self.register(VoiceProvider())
        self.register(MusicProvider())


    def list_providers(self):

        return [
            provider.status()
            for provider in self.providers.values()
        ]


    def get(self, name):

        return self.providers.get(name)
