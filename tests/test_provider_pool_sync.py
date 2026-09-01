from core.ai_core.orchestration.provider_pool import ProviderPool
from core.ai_core.providers import VideoProvider
from core.ai_core.providers.provider_registry import ProviderRegistry


def test_provider_pool_sees_provider_registered_after_initialization():
    registry = ProviderRegistry()
    pool = ProviderPool(registry=registry)

    provider = VideoProvider()
    registry.register(provider)

    assert provider in pool.select_many()


def test_provider_pool_does_not_duplicate_registered_provider():
    registry = ProviderRegistry()
    pool = ProviderPool(registry=registry)

    provider = VideoProvider()

    pool.add_provider(provider)
    pool.add_provider(provider)

    assert pool.select_many().count(provider) == 1
