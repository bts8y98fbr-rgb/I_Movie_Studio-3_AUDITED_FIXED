from dataclasses import dataclass


@dataclass
class QualityProfile:

    name: str
    resolution: str
    fps: int
    hdr: bool
    color_depth: int
    allow_downgrade: bool
    priority: list



class QualityPolicy:


    def __init__(
        self,
        profile="cinema_master"
    ):

        self.profiles = {

            "cinema_master": QualityProfile(

                name="Cinema Master 8K",

                resolution="7680x4320",

                fps=60,

                hdr=True,

                color_depth=10,

                allow_downgrade=False,

                priority=[

                    "quality",

                    "realism",

                    "cinematic_motion",

                    "detail"

                ]

            ),


            "preview": QualityProfile(

                name="Preview",

                resolution="1920x1080",

                fps=30,

                hdr=False,

                color_depth=8,

                allow_downgrade=True,

                priority=[

                    "speed"

                ]

            )

        }


        self.active_profile = (
            self.profiles[profile]
        )



    def get_profile(self):

        return {

            "name":
                self.active_profile.name,


            "resolution":
                self.active_profile.resolution,


            "fps":
                self.active_profile.fps,


            "hdr":
                self.active_profile.hdr,


            "color_depth":
                self.active_profile.color_depth,


            "allow_downgrade":
                self.active_profile.allow_downgrade,


            "priority":
                self.active_profile.priority

        }



    def validate_quality(
        self,
        requested
    ):


        required = self.active_profile


        errors = []


        if requested.get(
            "resolution"
        ) != required.resolution:

            if not required.allow_downgrade:

                errors.append(
                    "Resolution downgrade forbidden"
                )


        if requested.get(
            "fps"
        ) < required.fps:

            if not required.allow_downgrade:

                errors.append(
                    "FPS downgrade forbidden"
                )


        if required.hdr and not requested.get(
            "hdr",
            False
        ):

            errors.append(
                "HDR required"
            )


        return {

            "status":
                "approved"
                if not errors
                else "rejected",


            "errors":
                errors

        }
