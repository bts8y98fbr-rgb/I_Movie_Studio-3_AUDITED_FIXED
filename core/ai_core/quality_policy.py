from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QualityProfile:
    name: str
    resolution: str
    fps: int
    hdr: bool
    color_depth: int
    allow_downgrade: bool
    priority: list[str]


class QualityPolicy:
    """
    Global production-quality policy.

    The requested quality is a target, not a reason to stop generation.
    When a provider cannot satisfy the target, the caller can resolve the
    highest available capability and notify the user.
    """

    def __init__(self, profile: str = "production") -> None:
        self.profiles = {
            "production": QualityProfile(
                name="Production 4K",
                resolution="3840x2160",
                fps=60,
                hdr=True,
                color_depth=10,
                allow_downgrade=True,
                priority=[
                    "quality",
                    "realism",
                    "cinematic_motion",
                    "detail",
                ],
            ),
            # Backward-compatible alias used by the original project.
            "cinema_master": QualityProfile(
                name="Production 4K",
                resolution="3840x2160",
                fps=60,
                hdr=True,
                color_depth=10,
                allow_downgrade=True,
                priority=[
                    "quality",
                    "realism",
                    "cinematic_motion",
                    "detail",
                ],
            ),
            "preview": QualityProfile(
                name="Preview",
                resolution="1920x1080",
                fps=30,
                hdr=False,
                color_depth=8,
                allow_downgrade=True,
                priority=["speed"],
            ),
        }

        if profile not in self.profiles:
            raise ValueError(f"Unknown quality profile: {profile}")

        self.active_profile = self.profiles[profile]

        self.audio_defaults = {
            "quality": "high",
            "channels": 2,
            "channel_layout": "stereo",
        }

    def get_profile(self) -> dict[str, Any]:
        return {
            "name": self.active_profile.name,
            "resolution": self.active_profile.resolution,
            "fps": self.active_profile.fps,
            "hdr": self.active_profile.hdr,
            "color_depth": self.active_profile.color_depth,
            "allow_downgrade": self.active_profile.allow_downgrade,
            "priority": self.active_profile.priority,
        }

    def get_audio_defaults(self) -> dict[str, Any]:
        return dict(self.audio_defaults)

    def get_video_defaults(self) -> dict[str, Any]:
        return {
            "resolution": self.active_profile.resolution,
            "fps": self.active_profile.fps,
            "hdr": self.active_profile.hdr,
            "color_depth": self.active_profile.color_depth,
        }

    def validate_quality(self, requested: dict[str, Any]) -> dict[str, Any]:
        """
        Validate a requested quality against the active profile.

        This method remains backward-compatible with the original API:
        it returns ``approved`` or ``rejected`` plus an error list.

        New routing code should use ``resolve_quality`` so that an unsupported
        capability can fall back instead of stopping the generation.
        """

        required = self.active_profile
        errors: list[str] = []

        if requested.get("resolution") != required.resolution:
            if not required.allow_downgrade:
                errors.append("Resolution downgrade forbidden")

        if requested.get("fps", 0) < required.fps:
            if not required.allow_downgrade:
                errors.append("FPS downgrade forbidden")

        if required.hdr and not requested.get("hdr", False):
            if not required.allow_downgrade:
                errors.append("HDR required")

        if requested.get("color_depth", required.color_depth) < required.color_depth:
            if not required.allow_downgrade:
                errors.append("Color depth downgrade forbidden")

        return {
            "status": "approved" if not errors else "rejected",
            "errors": errors,
        }

    def resolve_quality(
        self,
        capabilities: dict[str, Any],
        requested: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Resolve the highest quality available from a provider.

        Generation is never rejected merely because a provider cannot deliver
        the requested production target. The returned notification explains
        any fallback.
        """

        target = requested or self.get_video_defaults()

        resolutions = capabilities.get("resolutions", [])
        fps_values = capabilities.get("fps", [])
        hdr_values = capabilities.get("hdr", [])
        color_depth_values = capabilities.get("color_depth", [])

        actual_resolution = self._highest_resolution(
            target.get("resolution"),
            resolutions,
        )
        actual_fps = self._highest_not_exceeding_or_highest(
            target.get("fps"),
            fps_values,
            default=target.get("fps", 60),
        )
        actual_hdr = self._resolve_bool_capability(
            target.get("hdr", True),
            hdr_values,
        )
        actual_color_depth = self._highest_not_exceeding_or_highest(
            target.get("color_depth", 10),
            color_depth_values,
            default=target.get("color_depth", 10),
        )

        actual = {
            "resolution": actual_resolution,
            "fps": actual_fps,
            "hdr": actual_hdr,
            "color_depth": actual_color_depth,
        }

        fallback = actual != target

        return {
            "status": "fallback" if fallback else "approved",
            "requested_quality": dict(target),
            "actual_quality": actual,
            "fallback_applied": fallback,
            "notification": (
                "Requested quality was not fully available. "
                "Generation will continue using the highest available capability."
                if fallback
                else None
            ),
        }

    @staticmethod
    def _highest_resolution(
        requested: str | None,
        available: list[str],
    ) -> str | None:
        if not available:
            return requested

        def pixels(value: str) -> int:
            try:
                width, height = value.lower().split("x")
                return int(width) * int(height)
            except (ValueError, AttributeError):
                return 0

        requested_pixels = pixels(requested) if requested else 0

        lower_or_equal = [
            value for value in available
            if pixels(value) <= requested_pixels and pixels(value) > 0
        ]

        if lower_or_equal:
            return max(lower_or_equal, key=pixels)

        return max(available, key=pixels)

    @staticmethod
    def _highest_not_exceeding_or_highest(
        requested: int,
        available: list[int],
        default: int,
    ) -> int:
        if not available:
            return default

        lower_or_equal = [
            value for value in available
            if value <= requested
        ]

        return max(lower_or_equal or available)

    @staticmethod
    def _resolve_bool_capability(
        requested: bool,
        available: list[bool],
    ) -> bool:
        if not available:
            return requested

        if requested in available:
            return requested

        return max(available)
