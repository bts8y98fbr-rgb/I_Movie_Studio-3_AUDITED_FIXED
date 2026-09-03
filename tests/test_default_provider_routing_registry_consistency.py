from core.ai_core.providers.provider_definition import ProviderDefinition
from core.ai_core.providers.provider_router import ProviderRouter


class ControlledCatalog:
    def __init__(self, providers):
        self.providers = providers

    def list(self):
        return self.providers


def test_execution_availability_filters_candidates_before_scoring():
    unavailable_high_score = ProviderDefinition(
        name="Unavailable High Score",
        media_types=["video"],
        api_available=True,
        free_api=True,
        quality_score=10.0,
        speed_score=10.0,
        status="active",
    )
    available_lower_score = ProviderDefinition(
        name="Available Lower Score",
        media_types=["video"],
        api_available=True,
        free_api=True,
        quality_score=5.0,
        speed_score=5.0,
        status="active",
    )
    catalog = ControlledCatalog(
        [unavailable_high_score, available_lower_score]
    )

    router = ProviderRouter(
        catalog,
        execution_available=lambda name: name == available_lower_score.name,
    )

    selected = router.select("video", mode="free")

    assert selected is available_lower_score

    unavailable_router = ProviderRouter(
        catalog,
        execution_available=lambda name: False,
    )

    assert unavailable_router.select("video", mode="free") is None


def test_default_router_returns_only_registered_execution_backend(tmp_path):
    from core.movie_engine.generation_engine import GenerationEngine

    engine = GenerationEngine(project_path=tmp_path, quality="4k")

    routed_provider = engine.provider_router.select("video", mode="free")

    if routed_provider is None:
        return

    execution_backend = engine.provider_manager.get(routed_provider.name)

    assert execution_backend is not None
    assert execution_backend.name == routed_provider.name
