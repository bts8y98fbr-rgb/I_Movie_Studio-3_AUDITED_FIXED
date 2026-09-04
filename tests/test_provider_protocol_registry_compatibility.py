from core.ai_core.providers.provider_registry import ProviderRegistry
from core.ai_core.providers.video.base_video_provider import BaseVideoProvider
from core.ai_core.providers.video.remote_video_provider import RemoteVideoProvider


def test_remote_video_provider_registers_without_identity_mutation():
    provider = RemoteVideoProvider(name="requested-video-provider")
    registry = ProviderRegistry()

    assert isinstance(provider, BaseVideoProvider)
    assert provider.name == "requested-video-provider"

    registered_provider = registry.register(provider)

    assert registered_provider is provider
    assert provider.name == "requested-video-provider"
    assert registry.get(provider.name) is provider
