import json

from core.ai_core.model_router import ModelRouter
from core.ai_core.quality_policy import QualityPolicy
from core.ai_core.shot_model_selector import ShotModelSelector


ROUTING_DIAGNOSTIC_KEYS = {
    "status",
    "requested_quality",
    "actual_quality",
    "fallback_applied",
    "notification",
    "time",
}


def assert_canonical_selection(result, expected_profile):
    assert result["shot_profile"] == expected_profile

    selected_model = result["selected_model"]
    assert isinstance(selected_model, dict)
    assert isinstance(selected_model["name"], str)
    assert selected_model["name"]
    assert "selected_model" not in selected_model

    routing_diagnostics = result["routing_diagnostics"]
    assert set(routing_diagnostics) == ROUTING_DIAGNOSTIC_KEYS
    assert isinstance(routing_diagnostics["time"], str)


def test_wide_shot_selects_environment_profile():

    router = ModelRouter(
        QualityPolicy()
    )

    selector = ShotModelSelector(
        router
    )

    result = selector.select_for_shot(
        {
            "camera": {
                "shot_type": "wide_establishing",
                "movement": "slow_pan",
            }
        }
    )

    assert_canonical_selection(result, "environment")



def test_action_shot_selects_motion_profile():

    router = ModelRouter(
        QualityPolicy()
    )

    selector = ShotModelSelector(
        router
    )

    result = selector.select_for_shot(
        {
            "camera": {
                "shot_type": "hero_reveal",
                "movement": "fast_motion",
            }
        }
    )

    assert_canonical_selection(result, "motion")



def test_close_detail_selects_detail_profile():

    router = ModelRouter(
        QualityPolicy()
    )

    selector = ShotModelSelector(
        router
    )

    result = selector.select_for_shot(
        {
            "camera": {
                "shot_type": "close_detail",
                "movement": "static",
            }
        }
    )

    assert_canonical_selection(result, "detail")
