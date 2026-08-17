from datetime import datetime


class ModelRouter:

    def __init__(self, quality_policy):
        self.quality_policy = quality_policy

        self.models = {
            "video": [
                {
                    "name": "cinematic_video_ultra",
                    "type": "video",
                    "quality": 10,
                    "motion": 10,
                    "realism": 10,
                    "detail": 10,
                    "profiles": [
                        "cinematic",
                        "environment",
                        "detail",
                    ],
                    "resolutions": [
                        "7680x4320",
                        "3840x2160",
                    ],
                    "fps": [
                        24,
                        30,
                        60,
                    ],
                    "hdr": [
                        True,
                    ],
                    "color_depth": [
                        10,
                    ],
                },
                {
                    "name": "cinematic_video_motion",
                    "type": "video",
                    "quality": 8,
                    "motion": 10,
                    "realism": 8,
                    "detail": 7,
                    "profiles": [
                        "motion",
                    ],
                    "resolutions": [
                        "3840x2160",
                        "1920x1080",
                    ],
                    "fps": [
                        60,
                    ],
                    "hdr": [
                        True,
                    ],
                    "color_depth": [
                        10,
                    ],
                },
                {
                    "name": "cinematic_video_detail",
                    "type": "video",
                    "quality": 9,
                    "motion": 7,
                    "realism": 10,
                    "detail": 10,
                    "profiles": [
                        "detail",
                    ],
                    "resolutions": [
                        "3840x2160",
                    ],
                    "fps": [
                        24,
                        30,
                    ],
                    "hdr": [
                        True,
                    ],
                    "color_depth": [
                        10,
                    ],
                },
            ],

            "image": [
                {
                    "name": "image_master",
                    "type": "image",
                    "quality": 10,
                    "realism": 10,
                    "detail": 10,
                    "hdr": [
                        True,
                    ],
                    "color_depth": [
                        10,
                    ],
                }
            ],
        }


    def get_best_model(
        self,
        media_type="video",
        shot_context=None,
    ):

        profile = self.quality_policy.get_profile()

        available = self.models.get(
            media_type,
            [],
        )


        if not available:
            return {
                "status": "error",
                "message": (
                    f"No models available for media type: {media_type}"
                ),
            }


        candidates = []

        shot_profile = (
            shot_context or {}
        ).get(
            "profile",
            "cinematic",
        )


        for model in available:

            profiles = model.get(
                "profiles",
                [],
            )

            if profiles and shot_profile not in profiles:
                continue


            if (
                profile["hdr"]
                and not self._supports_hdr(model)
            ):
                continue


            candidates.append(model)


        if not candidates:
            candidates = available


        best = sorted(
            candidates,
            key=lambda model: self._score_model(
                model,
                shot_profile,
            ),
            reverse=True,
        )[0]


        quality_resolution = (
            self._resolve_model_quality(
                best,
                profile,
            )
        )


        return {

            "status":
                quality_resolution["status"],


            "selected_model":
                best,


            "shot_profile":
                shot_profile,


            "requested_quality":
                quality_resolution["requested_quality"],


            "actual_quality":
                quality_resolution["actual_quality"],


            "fallback_applied":
                quality_resolution["fallback_applied"],


            "notification":
                quality_resolution["notification"],


            "time":
                datetime.now().isoformat(),

        }



    def _score_model(
        self,
        model,
        profile,
    ):

        if profile == "motion":
            return (
                model.get("motion", 0),
                model.get("quality", 0),
                model.get("realism", 0),
            )


        if profile == "detail":
            return (
                model.get("detail", 0),
                model.get("realism", 0),
                model.get("quality", 0),
            )


        if profile == "environment":
            return (
                model.get("realism", 0),
                model.get("detail", 0),
                model.get("quality", 0),
            )


        return (
            model.get("quality", 0),
            model.get("realism", 0),
            model.get("motion", 0),
        )



    def _resolve_model_quality(
        self,
        model,
        profile,
    ):

        capabilities = {

            "resolutions":
                model.get(
                    "resolutions",
                    [],
                ),

            "fps":
                model.get(
                    "fps",
                    [],
                ),

            "hdr":
                model.get(
                    "hdr",
                    [],
                ),

            "color_depth":
                model.get(
                    "color_depth",
                    [],
                ),

        }


        return self.quality_policy.resolve_quality(
            capabilities=capabilities,
            requested={
                "resolution":
                    profile["resolution"],

                "fps":
                    profile["fps"],

                "hdr":
                    profile["hdr"],

                "color_depth":
                    profile["color_depth"],
            },
        )



    @staticmethod
    def _supports_hdr(model):

        hdr = model.get(
            "hdr",
            False,
        )

        if isinstance(
            hdr,
            list,
        ):
            return True in hdr

        return bool(hdr)
