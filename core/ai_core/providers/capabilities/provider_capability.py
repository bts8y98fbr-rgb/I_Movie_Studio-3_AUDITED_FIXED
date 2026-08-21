from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ProviderCapability:
    """
    Describes what an AI provider can produce.

    Used by CapabilityMatcher and ProviderPool
    to select the best provider for a task.
    """

    provider_name: str

    media_type: str

    supported_qualities: List[str] = field(
        default_factory=list
    )

    max_duration_seconds: int = 0

    supports_hdr: bool = False

    supports_cinematic_style: bool = False

    supports_animation_style: bool = False

    supports_realistic_style: bool = False

    max_parallel_jobs: int = 1

    speed_score: int = 50

    quality_score: int = 50

    reliability_score: int = 50


    def supports_quality(
        self,
        quality: str,
    ) -> bool:
        return quality in self.supported_qualities


    def can_handle_duration(
        self,
        duration: int,
    ) -> bool:
        if self.max_duration_seconds <= 0:
            return True

        return duration <= self.max_duration_seconds


    def score(self) -> int:
        """
        Overall provider capability score.
        """

        return (
            self.speed_score
            +
            self.quality_score
            +
            self.reliability_score
        )
