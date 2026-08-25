from core.ai_core.model_policy import (
    ModelPolicy,
    SelectionMode,
)


def test_fixed_policy_allows_only_selected_model():

    policy = ModelPolicy(
        provider="WaveSpeed",
        model="kling-video",
        mode=SelectionMode.FIXED,
    )

    assert policy.allows(
        "WaveSpeed",
        "kling-video",
    )

    assert not policy.allows(
        "WaveSpeed",
        "other-video",
    )

    assert not policy.allows(
        "Direct API",
        "kling-video",
    )


def test_preferred_policy_allows_only_approved_models():

    policy = ModelPolicy(
        mode=SelectionMode.PREFERRED,
        approved_models=[
            "kling-video",
            "runway-video",
        ],
    )

    assert policy.allows(
        "WaveSpeed",
        "kling-video",
    )

    assert policy.allows(
        "Direct API",
        "runway-video",
    )

    assert not policy.allows(
        "WaveSpeed",
        "unknown-video",
    )


def test_automatic_policy_allows_router_selection():

    policy = ModelPolicy(
        mode=SelectionMode.AUTOMATIC,
    )

    assert policy.allows(
        "WaveSpeed",
        "any-model",
    )
