from dataclasses import asdict

from core.ai_core.runtime.capabilities import (
    CapabilityEvaluator,
)
from core.ai_core.runtime.hardware import (
    HardwareDetector,
)


class RuntimePolicy:
    """Central runtime decision point for cross-platform execution."""

    def __init__(
        self,
        hardware_detector=None,
        capability_evaluator=None,
    ):
        self.hardware_detector = (
            hardware_detector
            or HardwareDetector()
        )

        self.capability_evaluator = (
            capability_evaluator
            or CapabilityEvaluator()
        )

        self.hardware = (
            self.hardware_detector.detect()
        )

        self.capabilities = (
            self.capability_evaluator.evaluate(
                self.hardware
            )
        )

    def snapshot(self) -> dict:
        return {
            "hardware": {
                key: value
                for key, value
                in self.hardware.__dict__.items()
            },
            "capabilities": asdict(
                self.capabilities
            ),
        }

    def should_use_local_llm(
        self,
        preference="auto",
    ) -> bool:
        if preference == "never":
            return False

        if preference == "always":
            return self.capabilities.can_run_local_llm

        return (
            self.capabilities.recommended_local_llm
        )

    def max_parallel_tasks(self) -> int:
        return self.capabilities.max_parallel_tasks
