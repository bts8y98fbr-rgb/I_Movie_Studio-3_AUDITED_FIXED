from types import SimpleNamespace

from core.ai_core.runtime import (
    CapabilityEvaluator,
    RuntimePolicy,
)


def test_low_end_machine_disables_local_llm():
    hardware = SimpleNamespace(
        cpu_cores=4,
        memory_gb=8,
    )

    capabilities = CapabilityEvaluator().evaluate(
        hardware
    )

    assert capabilities.can_run_application is True
    assert capabilities.can_run_local_llm is False
    assert capabilities.recommended_local_llm is False
    assert capabilities.max_parallel_tasks == 2


def test_minimum_local_llm_machine():
    hardware = SimpleNamespace(
        cpu_cores=4,
        memory_gb=16,
    )

    capabilities = CapabilityEvaluator().evaluate(
        hardware
    )

    assert capabilities.can_run_local_llm is True
    assert capabilities.recommended_local_llm is False


def test_good_machine_recommends_local_llm():
    hardware = SimpleNamespace(
        cpu_cores=8,
        memory_gb=32,
    )

    capabilities = CapabilityEvaluator().evaluate(
        hardware
    )

    assert capabilities.can_run_local_llm is True
    assert capabilities.recommended_local_llm is True
    assert capabilities.max_parallel_tasks == 4


def test_runtime_policy_auto_requires_recommended_hardware():
    hardware_detector = SimpleNamespace(
        detect=lambda: SimpleNamespace(
            cpu_cores=4,
            memory_gb=16,
        )
    )

    policy = RuntimePolicy(
        hardware_detector=hardware_detector
    )

    assert policy.should_use_local_llm(
        "auto"
    ) is False


def test_runtime_policy_never_disables_local_llm():
    hardware_detector = SimpleNamespace(
        detect=lambda: SimpleNamespace(
            cpu_cores=16,
            memory_gb=64,
        )
    )

    policy = RuntimePolicy(
        hardware_detector=hardware_detector
    )

    assert policy.should_use_local_llm(
        "never"
    ) is False


def test_runtime_policy_always_uses_local_llm_when_supported():
    hardware_detector = SimpleNamespace(
        detect=lambda: SimpleNamespace(
            cpu_cores=8,
            memory_gb=32,
        )
    )

    policy = RuntimePolicy(
        hardware_detector=hardware_detector
    )

    assert policy.should_use_local_llm(
        "always"
    ) is True
