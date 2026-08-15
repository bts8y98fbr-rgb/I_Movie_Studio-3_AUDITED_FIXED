from dataclasses import dataclass


@dataclass
class QualityProfile:

    name: str
    width: int
    height: int
    fps: int
    hdr: bool
    color_depth: int


class QualityManager:


    PROFILES = {

        "preview": QualityProfile(
            "Preview",
            1280,
            720,
            24,
            False,
            8
        ),


        "hd": QualityProfile(
            "HD",
            1920,
            1080,
            24,
            False,
            8
        ),


        "4k": QualityProfile(
            "Ultra 4K",
            3840,
            2160,
            60,
            True,
            10
        ),


        "8k": QualityProfile(
            "Master 8K",
            7680,
            4320,
            60,
            True,
            10
        )

    }


    def __init__(self, quality="4k"):

        if quality not in self.PROFILES:
            raise ValueError(
                f"Unknown quality profile: {quality}"
            )

        self.profile = self.PROFILES[quality]


    def get_settings(self):

        return {

            "quality": self.profile.name,

            "resolution": (
                f"{self.profile.width}x"
                f"{self.profile.height}"
            ),

            "fps": self.profile.fps,

            "hdr": self.profile.hdr,

            "color_depth": self.profile.color_depth

        }
