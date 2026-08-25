import json

from core.ai_core.model_router import ModelRouter
from core.ai_core.quality_policy import QualityPolicy
from core.ai_core.shot_model_selector import ShotModelSelector


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

    assert result["shot_profile"] == "environment"

    assert (
        result["selected_model"]["shot_profile"]
        == "environment"
    )



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

    assert result["shot_profile"] == "motion"

    assert (
        result["selected_model"]["shot_profile"]
        == "motion"
    )



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

    assert result["shot_profile"] == "detail"

    assert (
        result["selected_model"]["shot_profile"]
        == "detail"
    )
