from core.ai_core.quality_policy import QualityPolicy
from core.ai_core.model_router import ModelRouter


def test_production_defaults_are_4k_60_hdr_10bit():
    policy = QualityPolicy()

    video = policy.get_video_defaults()

    assert video == {
        "resolution": "3840x2160",
        "fps": 60,
        "hdr": True,
        "color_depth": 10,
    }


def test_audio_defaults_are_high_quality_stereo():
    policy = QualityPolicy()

    audio = policy.get_audio_defaults()

    assert audio["quality"] == "high"
    assert audio["channels"] == 2
    assert audio["channel_layout"] == "stereo"


def test_quality_policy_falls_back_without_rejecting_generation():
    policy = QualityPolicy()

    result = policy.resolve_quality(
        capabilities={
            "resolutions": ["1920x1080"],
            "fps": [30],
            "hdr": [False],
            "color_depth": [8],
        }
    )

    assert result["status"] == "fallback"
    assert result["fallback_applied"] is True
    assert result["actual_quality"] == {
        "resolution": "1920x1080",
        "fps": 30,
        "hdr": False,
        "color_depth": 8,
    }
    assert result["notification"]


def test_model_router_returns_requested_and_actual_quality():
    policy = QualityPolicy()
    router = ModelRouter(policy)

    result = router.get_best_model("video")

    assert result["status"] in {"approved", "fallback"}
    assert result["selected_model"]["name"]
    assert result["requested_quality"]["resolution"] == "3840x2160"
    assert result["requested_quality"]["fps"] == 60
    assert "actual_quality" in result
    assert "fallback_applied" in result
    assert "notification" in result


def test_model_router_keeps_generation_routable_when_4k_is_unavailable():
    policy = QualityPolicy()
    router = ModelRouter(policy)

    router.models["video"] = [
        {
            "name": "limited_video",
            "type": "video",
            "quality": 7,
            "motion": 7,
            "realism": 7,
            "resolutions": ["1920x1080"],
            "fps": [30],
            "hdr": [True],
            "color_depth": [8],
        }
    ]

    result = router.get_best_model("video")

    assert result["status"] == "fallback"
    assert result["selected_model"]["name"] == "limited_video"
    assert result["fallback_applied"] is True
    assert result["actual_quality"]["resolution"] == "1920x1080"
    assert result["actual_quality"]["fps"] == 30
    assert result["actual_quality"]["color_depth"] == 8


def test_provider_registry_register_get_and_unregister():
    from core.ai_core.providers import VideoProvider
    from core.ai_core.providers.provider_registry import ProviderRegistry

    registry = ProviderRegistry()
    provider = VideoProvider()

    assert registry.register(provider) is provider
    assert registry.get("Video AI") is provider
    assert registry.list_names() == ["Video AI"]
    assert registry.list_providers() == [provider]

    assert registry.unregister("Video AI") is provider
    assert registry.get("Video AI") is None
    assert registry.list_names() == []


def test_provider_manager_uses_injected_registry():
    from core.ai_core.provider_manager import ProviderManager
    from core.ai_core.providers.provider_registry import ProviderRegistry

    registry = ProviderRegistry()
    manager = ProviderManager(registry)

    manager.load_default_providers()

    assert manager.registry is registry
    assert manager.get("Video AI") is registry.get("Video AI")
    assert len(manager.list_providers()) == 4


def test_provider_manager_can_unregister_provider():
    from core.ai_core.provider_manager import ProviderManager

    manager = ProviderManager()
    manager.load_default_providers()

    removed = manager.unregister("Video AI")

    assert removed is not None
    assert removed.name == "Video AI"
    assert manager.get("Video AI") is None
    assert len(manager.list_providers()) == 3
