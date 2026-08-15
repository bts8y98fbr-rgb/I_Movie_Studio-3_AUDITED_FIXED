import pytest

pytest.importorskip("PyQt6")

from ui.main_window import NAVIGATION, MainWindow, ModelPolicy, SelectionMode


def test_navigation_contains_required_workspaces(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    labels = [window.navigation.item(i).text() for i in range(window.navigation.count())]
    assert labels == list(NAVIGATION)
    assert "AI Models" in labels


def test_fixed_model_policy_blocks_other_models():
    policy = ModelPolicy(provider="WaveSpeed", model="kling-video", mode=SelectionMode.FIXED)
    assert policy.allows("WaveSpeed", "kling-video")
    assert not policy.allows("WaveSpeed", "other-video")
    assert not policy.allows("Direct API", "kling-video")
