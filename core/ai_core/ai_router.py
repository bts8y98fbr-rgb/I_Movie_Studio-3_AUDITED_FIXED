from core.ai_core.providers import (
    ImageProvider,
    VideoProvider,
    VoiceProvider,
    MusicProvider
)


class AIRouter:

    def __init__(self):
        self.providers = {
            "image": ImageProvider(),
            "video": VideoProvider(),
            "voice": VoiceProvider(),
            "music": MusicProvider()
        }


    def get_provider(self, provider_type):

        provider = self.providers.get(provider_type)

        if provider is None:
            raise ValueError(
                f"Unknown AI provider: {provider_type}"
            )

        return provider


    def list_available(self):
        return [
            provider.status()
            for provider in self.providers.values()
        ]
