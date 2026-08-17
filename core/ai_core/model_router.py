from datetime import datetime

from core.ai_core.model_policy import SelectionMode


class ModelRouter:

    def __init__(self, quality_policy, model_policy=None):
        self.quality_policy = quality_policy
        self.model_policy = model_policy

        self.models = {
            "video": [
                {
                    "name": "cinematic_video_ultra",
                    "type": "video",
                    "quality": 10,
                    "motion": 10,
                    "realism": 10,
                    "resolutions": [
                        "7680x4320",
                        "3840x2160",
                    ],
                    "fps": [24, 30, 60],
                    "hdr": [True],
                    "color_depth": [10],
                },
                {
                    "name": "cinematic_video_pro",
                    "type": "video",
                    "quality": 8,
                    "motion": 9,
                    "realism": 8,
                    "resolutions": [
                        "3840x2160",
                        "1920x1080",
                    ],
                    "fps": [24, 30, 60],
                    "hdr": [True],
                    "color_depth": [10],
                },
            ],

            "image": [
                {
                    "name": "image_master",
                    "type": "image",
                    "quality": 10,
                    "realism": 10,
                    "hdr": [True],
                    "color_depth": [10],
                }
            ],
        }


    def get_best_model(self, media_type="video"):

        profile = self.quality_policy.get_profile()

        available = self.models.get(media_type, [])

        if not available:
            return {
                "status": "error",
                "message": f"No models available for {media_type}",
            }


        candidates = [
            model
            for model in available
            if (
                not profile["hdr"]
                or self._supports_hdr(model)
            )
        ]


        if not candidates:
            return {
                "status": "error",
                "message": "No compatible models",
            }


        selected = self._apply_model_policy(
            candidates,
            media_type,
        )


        quality = self._resolve_model_quality(
            selected,
            profile,
        )


        return {
            "status": quality["status"],
            "selected_model": selected,
            "requested_quality": quality["requested_quality"],
            "actual_quality": quality["actual_quality"],
            "fallback_applied": quality["fallback_applied"],
            "notification": quality["notification"],
            "time": datetime.now().isoformat(),
        }



    def _apply_model_policy(
        self,
        candidates,
        media_type,
    ):

        if self.model_policy is None:
            return self._best(candidates)


        mode = self.model_policy.mode


        if mode == SelectionMode.FIXED:

            for model in candidates:
                if self.model_policy.allows(
                    self.model_policy.provider,
                    model["name"],
                ):
                    return model


            return self._best(candidates)


        if mode == SelectionMode.PREFERRED:

            for preferred in self.model_policy.models:

                for model in candidates:
                    if model["name"] == preferred:
                        return model


            return self._best(candidates)


        return self._best(candidates)



    @staticmethod
    def _best(models):

        return sorted(
            models,
            key=lambda model: (
                model.get("quality", 0),
                model.get("realism", 0),
                model.get("motion", 0),
            ),
            reverse=True,
        )[0]



    def _resolve_model_quality(
        self,
        model,
        profile,
    ):

        capabilities = {
            "resolutions": model.get(
                "resolutions",
                [],
            ),
            "fps": model.get(
                "fps",
                [],
            ),
            "hdr": model.get(
                "hdr",
                [],
            ),
            "color_depth": model.get(
                "color_depth",
                [],
            ),
        }


        return self.quality_policy.resolve_quality(
            capabilities=capabilities,
            requested={
                "resolution": profile["resolution"],
                "fps": profile["fps"],
                "hdr": profile["hdr"],
                "color_depth": profile["color_depth"],
            },
        )



    @staticmethod
    def _supports_hdr(model):

        hdr = model.get(
            "hdr",
            False,
        )

        if isinstance(hdr, list):
            return True in hdr

        return bool(hdr)
