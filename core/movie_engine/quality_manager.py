from dataclasses import dataclass


@dataclass(frozen=True)
class QualityProfile:
    name: str
    width: int
    height: int
    fps: int
    hdr: bool
    color_depth: int


class QualityManager:
    """
    User-facing video quality selection.

    4K is the default production target.
    8K remains a valid user choice. Provider capability resolution is handled
    later by QualityPolicy; this class must not silently downgrade 8K.
    """

    PROFILES = {
        "preview": QualityProfile("Preview", 1280, 720, 24, False, 8),
        "hd": QualityProfile("HD", 1920, 1080, 24, False, 8),
        "4k": QualityProfile("Production 4K", 3840, 2160, 60, True, 10),
        "production": QualityProfile("Production 4K", 3840, 2160, 60, True, 10),
        "8k": QualityProfile("Master 8K", 7680, 4320, 60, True, 10),
    }

    def __init__(self, quality="4k"):
        if quality not in self.PROFILES:
            raise ValueError(f"Unknown quality profile: {quality}")

        self.requested_quality = quality
        self.profile = self.PROFILES[quality]

    def get_settings(self):
        return {
            "quality": self.profile.name,
            "resolution": f"{self.profile.width}x{self.profile.height}",
            "fps": self.profile.fps,
            "hdr": self.profile.hdr,
            "color_depth": self.profile.color_depth,
        }
