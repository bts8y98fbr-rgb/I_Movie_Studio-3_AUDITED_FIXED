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
    Video quality policy.

    Default:
        4K

    Available:
        1080p
        2K
        4K
        8K

    Provider limitations never stop generation.
    System selects the highest supported quality below target.
    """

    def __init__(self, profile: str = "4k") -> None:

        self.profiles = {

            "1080p": QualityProfile(
                "Full HD 1080p",
                "1920x1080",
                30,
                False,
                8,
                True,
                ["speed"],
            ),

            "2k": QualityProfile(
                "Cinema 2K",
                "2048x1080",
                60,
                True,
                10,
                True,
                [
                    "quality",
                    "realism",
                    "cinematic_motion",
                ],
            ),

            "4k": QualityProfile(
                "Production 4K",
                "3840x2160",
                60,
                True,
                10,
                True,
                [
                    "quality",
                    "realism",
                    "cinematic_motion",
                    "detail",
                ],
            ),

            "production": QualityProfile(
                "Production 4K",
                "3840x2160",
                60,
                True,
                10,
                True,
                [
                    "quality",
                    "realism",
                    "cinematic_motion",
                    "detail",
                ],
            ),

            "8k": QualityProfile(
                "Master 8K",
                "7680x4320",
                60,
                True,
                10,
                True,
                [
                    "quality",
                    "realism",
                    "cinematic_motion",
                    "detail",
                ],
            ),
        }


        if profile not in self.profiles:
            raise ValueError(
                f"Unknown quality profile: {profile}"
            )

        self.active_profile = self.profiles[profile]


    def get_available_profiles(self):

        return [
            {
                "id": key,
                "name": value.name,
                "resolution": value.resolution,
            }
            for key, value in self.profiles.items()
            if key != "production"
        ]


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


    def get_video_defaults(self):

        return {
            "resolution": self.active_profile.resolution,
            "fps": self.active_profile.fps,
            "hdr": self.active_profile.hdr,
            "color_depth": self.active_profile.color_depth,
        }


    def get_audio_defaults(self):

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
    ):
        target = dict(
            requested or self.get_video_defaults()
        )

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
            "hdr": (
                target.get("hdr", True)
                if target.get("hdr", True) in capabilities.get("hdr", [])
                else capabilities.get("hdr", [False])[0]
            ),
            "color_depth": (
                target.get("color_depth", 10)
                if target.get("color_depth", 10) in capabilities.get("color_depth", [])
                else max(capabilities.get("color_depth", [8]))
            ),
        }

        fallback = actual != target

        return {
            "status": "fallback" if fallback else "approved",
            "requested_quality": target,
            "actual_quality": actual,
            "fallback_applied": fallback,
            "notification": (
                "Requested quality was reduced to "
                "the highest supported provider capability."
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
                w,h = str(value).split("x")
                return int(w)*int(h)

            except Exception:
                return 0


        target = pixels(requested)


        possible = [
            x for x in available
            if pixels(x)<=target
        ]


        return (
            max(
                possible,
                key=pixels
            )
            if possible
            else max(
                available,
                key=pixels
            )
        )


    @staticmethod
    def _highest_not_exceeding_or_highest(
        requested,
        available,
        fallback,
    ):

        if not available:
            return fallback

        lower = [
            x for x in available
            if x<=requested
        ]

        return (
            max(lower)
            if lower
            else max(available)
        )
