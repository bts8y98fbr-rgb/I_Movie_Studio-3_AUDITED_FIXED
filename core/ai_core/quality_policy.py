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
    Resolves a user's requested target against real provider capabilities.

    Default target is Production 4K. 8K is a valid explicit user choice.
    A provider limitation never stops generation: the highest supported
    capability at or below the requested target is selected and a notification
    is returned when fallback was necessary.
    """

    def __init__(self, profile: str = "production") -> None:
        self.profiles = {
            "production": QualityProfile(
                "Production 4K",
                "3840x2160",
                60,
                True,
                10,
                True,
                ["quality", "realism", "cinematic_motion", "detail"],
            ),
            "4k": QualityProfile(
                "Production 4K",
                "3840x2160",
                60,
                True,
                10,
                True,
                ["quality", "realism", "cinematic_motion", "detail"],
            ),
            "8k": QualityProfile(
                "Master 8K",
                "7680x4320",
                60,
                True,
                10,
                True,
                ["quality", "realism", "cinematic_motion", "detail"],
            ),
            "preview": QualityProfile(
                "Preview",
                "1920x1080",
                30,
                False,
                8,
                True,
                ["speed"],
            ),
        }

        if profile not in self.profiles:
            raise ValueError(f"Unknown quality profile: {profile}")

        self.active_profile = self.profiles[profile]

    def get_profile(self) -> dict[str, Any]:
        return {
            "name": self.active_profile.name,
            "resolution": self.active_profile.resolution,
            "fps": self.active_profile.fps,
            "hdr": self.active_profile.hdr,
            "color_depth": self.active_profile.color_depth,
            "allow_downgrade": self.active_profile.allow_downgrade,
            "priority": list(self.active_profile.priority),
        }

    def get_video_defaults(self) -> dict[str, Any]:
        return {
            "resolution": self.active_profile.resolution,
            "fps": self.active_profile.fps,
            "hdr": self.active_profile.hdr,
            "color_depth": self.active_profile.color_depth,
        }

    def get_audio_defaults(self) -> dict[str, Any]:
        return {
            "format": "stereo",
            "channels": 2,
            "channel_layout": "stereo",
            "quality": "high",
        }

    def resolve_quality(
        self,
        capabilities: dict[str, Any],
        requested: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        target = dict(requested or self.get_video_defaults())

        actual = {
            "resolution": self._highest_resolution(
                target.get("resolution"),
                capabilities.get("resolutions", []),
            ),
            "fps": self._highest_not_exceeding_or_highest(
                target.get("fps", 60),
                capabilities.get("fps", []),
                target.get("fps", 60),
            ),
            "hdr": self._resolve_bool_capability(
                target.get("hdr", True),
                capabilities.get("hdr", []),
            ),
            "color_depth": self._highest_not_exceeding_or_highest(
                target.get("color_depth", 10),
                capabilities.get("color_depth", []),
                target.get("color_depth", 10),
            ),
        }

        fallback = actual != target

        return {
            "status": "fallback" if fallback else "approved",
            "requested_quality": target,
            "actual_quality": actual,
            "fallback_applied": fallback,
            "notification": (
                "Requested video quality is not fully supported by the "
                "selected provider. Generation will continue using the "
                "highest supported quality."
                if fallback
                else None
            ),
        }

    def resolve_audio(
        self,
        capabilities: dict[str, Any],
        requested: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Resolve audio without exceeding the system ceiling of DTS 9.1.

        Supported system order:
        stereo < 5.1 < 7.1 < dts_9.1
        """

        target = dict(requested or self.get_audio_defaults())

        formats = [
            str(value).lower()
            for value in capabilities.get("formats", [])
        ]

        if not formats:
            formats = ["stereo"]

        system_order = ["stereo", "5.1", "7.1", "dts_9.1"]
        ceiling = "dts_9.1"

        requested_format = str(
            target.get("format", "stereo")
        ).lower()

        if requested_format not in system_order:
            requested_format = "stereo"

        requested_rank = min(
            system_order.index(requested_format),
            system_order.index(ceiling),
        )

        supported = [
            fmt
            for fmt in formats
            if fmt in system_order
            and system_order.index(fmt) <= requested_rank
        ]

        actual_format = (
            max(supported, key=system_order.index)
            if supported
            else "stereo"
        )

        channel_map = {
            "stereo": 2,
            "5.1": 6,
            "7.1": 8,
            "dts_9.1": 10,
        }

        actual = {
            "format": actual_format,
            "channels": channel_map[actual_format],
            "channel_layout": actual_format,
            "quality": str(
                target.get("quality", "high")
            ).lower(),
        }

        fallback = (
            actual_format
            != str(target.get("format", "stereo")).lower()
            or int(
                target.get(
                    "channels",
                    channel_map[requested_format],
                )
            ) != actual["channels"]
        )

        return {
            "status": "fallback" if fallback else "approved",
            "requested_audio": target,
            "actual_audio": actual,
            "fallback_applied": fallback,
            "notification": (
                "Requested audio format is not fully supported by the "
                "selected provider. Generation will continue using the "
                "highest supported format up to DTS 9.1."
                if fallback
                else None
            ),
        }

    @staticmethod
    def _highest_resolution(requested, available):
        if not available:
            return requested

        def pixels(value):
            try:
                width, height = str(value).lower().split("x")
                return int(width) * int(height)
            except (ValueError, TypeError):
                return 0

        requested_pixels = pixels(requested)

        lower_or_equal = [
            value
            for value in available
            if 0 < pixels(value) <= requested_pixels
        ]

        return (
            max(lower_or_equal, key=pixels)
            if lower_or_equal
            else max(available, key=pixels)
        )

    @staticmethod
    def _highest_not_exceeding_or_highest(
        requested,
        available,
        default,
    ):
        if not available:
            return default

        lower_or_equal = [
            value for value in available if value <= requested
        ]

        return max(lower_or_equal or available)

    @staticmethod
    def _resolve_bool_capability(requested, available):
        if not available:
            return requested

        if requested in available:
            return requested

        return max(available)
