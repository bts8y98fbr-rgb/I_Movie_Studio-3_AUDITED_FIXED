from core.ai_core.providers.capabilities.capability_matcher import (
    CapabilityMatcher,
)
from core.ai_core.providers.capabilities.provider_capability import (
    ProviderCapability,
)


def test_matcher_keeps_injected_empty_capability_list():
    capabilities = []
    matcher = CapabilityMatcher(capabilities)

    capability = ProviderCapability(
        provider_name="Test Video Provider",
        media_type="video",
        supported_qualities=["720p"],
    )
    capabilities.append(capability)

    result = matcher.find_best(
        media_type="video",
        quality="720p",
    )

    assert result is capability
