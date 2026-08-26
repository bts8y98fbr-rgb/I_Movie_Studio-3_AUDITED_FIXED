from .provider_definition import ProviderDefinition


class ProviderCatalog:
    """Dynamic catalog of external AI providers.

    The catalog describes capabilities and availability.
    It does not contain user secrets.
    """

    def __init__(self):
        self._providers: dict[str, ProviderDefinition] = {}
        self._load_builtin_catalog()

    def register(self, provider: ProviderDefinition):
        self._providers[provider.name] = provider
        return provider

    def get(self, name: str):
        return self._providers.get(name)

    def list(self):
        return list(self._providers.values())

    def _load_builtin_catalog(self):
        self.register(
            ProviderDefinition(
                name="Gemini",
                media_types=["llm"],
                api_available=True,
                requires_key=True,
                free_api=True,
                quality_score=9.0,
                speed_score=8.0,
                status="active",
            )
        )

        self.register(
            ProviderDefinition(
                name="Groq",
                media_types=["llm", "audio"],
                api_available=True,
                requires_key=True,
                free_api=True,
                quality_score=8.5,
                speed_score=10.0,
                status="active",
            )
        )

        self.register(
            ProviderDefinition(
                name="OpenRouter",
                media_types=["llm", "image", "audio"],
                api_available=True,
                requires_key=True,
                free_api=True,
                quality_score=8.5,
                speed_score=8.0,
                status="active",
                metadata={
                    "free_router": "openrouter/free",
                    "dynamic_free_models": True,
                },
            )
        )

        self.register(
            ProviderDefinition(
                name="Hugging Face",
                media_types=["llm", "image", "audio"],
                api_available=True,
                requires_key=True,
                free_api=True,
                quality_score=8.0,
                speed_score=7.0,
                status="active",
            )
        )

        self.register(
            ProviderDefinition(
                name="Stability AI",
                media_types=["image", "audio"],
                api_available=True,
                requires_key=True,
                free_credits=True,
                quality_score=8.5,
                speed_score=8.0,
                status="active",
            )
        )

        self.register(
            ProviderDefinition(
                name="ElevenLabs",
                media_types=["voice"],
                api_available=True,
                requires_key=True,
                free_api=True,
                commercial_use=False,
                quality_score=9.5,
                speed_score=8.0,
                status="active",
            )
        )

        self.register(
            ProviderDefinition(
                name="PixVerse",
                media_types=["video"],
                api_available=True,
                requires_key=True,
                free_credits=True,
                quality_score=8.5,
                speed_score=8.0,
                status="active",
            )
        )
