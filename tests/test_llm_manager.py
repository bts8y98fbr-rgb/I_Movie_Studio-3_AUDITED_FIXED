from types import SimpleNamespace

from core.ai_core.llm import (
    LLMManager,
)


def test_manager_works_without_any_llm():
    runtime = SimpleNamespace(
        should_use_local_llm=lambda preference="auto": False
    )

    manager = LLMManager(
        runtime_policy=runtime
    )

    result = manager.generate(
        "Create a cinematic shot"
    )

    assert result["status"] == "unavailable"
    assert result["provider"] == "none"


def test_manager_uses_remote_backend_when_available():
    class FakeRemote:
        def generate(self, prompt, **kwargs):
            return {
                "status": "generated",
                "content": "remote result",
            }

    runtime = SimpleNamespace(
        should_use_local_llm=lambda preference="auto": False
    )

    manager = LLMManager(
        runtime_policy=runtime,
        remote_backend=FakeRemote(),
    )

    result = manager.generate(
        "Create a cinematic shot"
    )

    assert result["status"] == "generated"
    assert result["provider"] == "remote"
    assert result["content"] == "remote result"


def test_local_backend_is_not_used_when_runtime_rejects_it():
    class FakeLocal:
        def generate(self, prompt, **kwargs):
            return {
                "status": "generated",
                "content": "local result",
            }

    runtime = SimpleNamespace(
        should_use_local_llm=lambda preference="auto": False
    )

    manager = LLMManager(
        runtime_policy=runtime,
        local_backend=FakeLocal(),
    )

    result = manager.generate(
        "Create a cinematic shot"
    )

    assert result["provider"] == "none"


def test_local_backend_can_be_selected_explicitly():
    class FakeLocal:
        def generate(self, prompt, **kwargs):
            return {
                "status": "generated",
                "content": "local result",
            }

    runtime = SimpleNamespace(
        should_use_local_llm=lambda preference="auto": True
    )

    manager = LLMManager(
        runtime_policy=runtime,
        local_backend=FakeLocal(),
    )

    result = manager.generate(
        "Create a cinematic shot"
    )

    assert result["status"] == "generated"
    assert result["provider"] == "local"


def test_never_preference_disables_all_llm_backends():
    class FakeRemote:
        def generate(self, prompt, **kwargs):
            return {
                "status": "generated",
                "content": "remote result",
            }

    runtime = SimpleNamespace(
        should_use_local_llm=lambda preference="auto": True
    )

    manager = LLMManager(
        runtime_policy=runtime,
        remote_backend=FakeRemote(),
    )

    result = manager.generate(
        "Create a cinematic shot",
        preference="never",
    )

    assert result["provider"] == "none"
    assert result["status"] == "unavailable"
