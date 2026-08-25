from core.ai_core.providers.capabilities.provider_capability import (
    ProviderCapability,
)


class CapabilityMatcher:
    """
    Selects the best AI provider based on
    required generation capabilities.
    """

    def __init__(
        self,
        capabilities=None,
    ):
        self.capabilities = (
            capabilities
            or []
        )


    def register(
        self,
        capability: ProviderCapability,
    ):
        self.capabilities.append(
            capability
        )


    def find_best(
        self,
        media_type,
        quality,
        duration=0,
        hdr=False,
        style=None,
    ):

        candidates = []

        for capability in self.capabilities:

            if capability.media_type != media_type:
                continue

            score = capability.score()


            if not capability.supports_quality(
                quality
            ):
                score -= 100


            if not capability.can_handle_duration(
                duration
            ):
                score -= 50


            if hdr and not capability.supports_hdr:
                score -= 30


            if style == "cinematic":

                if capability.supports_cinematic_style:
                    score += 20
                else:
                    score -= 10


            if style == "animation":

                if capability.supports_animation_style:
                    score += 20


            if style == "realistic":

                if capability.supports_realistic_style:
                    score += 20


            candidates.append(
                (
                    score,
                    capability,
                )
            )


        if not candidates:
            return None


        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )


        return candidates[0][1]
