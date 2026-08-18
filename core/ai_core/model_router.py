from datetime import datetime


class ModelRouter:
    """
    Selects the best model for the requested shot profile while leaving
    capability fallback to QualityPolicy.
    """

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
                    "profiles": ["cinematic", "environment", "detail"],
                    "resolutions": ["7680x4320", "3840x2160"],
                    "fps": [24, 30, 60],
                    "hdr": [True],
                    "color_depth": [10],
                },
                {
                    "name": "cinematic_video_motion",
                    "type": "video",
                    "quality": 8,
                    "motion": 10,
                    "realism": 8,
                    "detail": 7,
                    "profiles": ["motion"],
                    "resolutions": ["3840x2160", "1920x1080"],
                    "fps": [60],
                    "hdr": [True],
                    "color_depth": [10],
                },
                {
                    "name": "cinematic_video_detail",
                    "type": "video",
                    "quality": 9,
                    "motion": 7,
                    "realism": 10,
                    "detail": 10,
                    "profiles": ["detail"],
                    "resolutions": ["3840x2160"],
                    "fps": [24, 30],
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
                    "detail": 10,
                    "profiles": ["cinematic", "environment", "detail"],
                    "resolutions": ["7680x4320", "3840x2160"],
                    "fps": [],
                    "hdr": [True],
                    "color_depth": [10],
                }
            ],
        }

    def get_best_model(self, media_type="video", shot_context=None):
        available = self.models.get(media_type, [])
        if not available:
            return {
                "status": "error",
                "message": f"No models available for media type: {media_type}",
            }

        shot_profile = (shot_context or {}).get("profile", "cinematic")
        candidates = [
            model for model in available
            if not model.get("profiles")
            or shot_profile in model.get("profiles", [])
        ]

        if not candidates:
            candidates = available

        best = sorted(
            candidates,
            key=lambda model: self._score_model(model, shot_profile),
            reverse=True,
        )[0]

        requested = self.quality_policy.get_video_defaults()
        resolution = self.quality_policy.resolve_quality(
            capabilities={
                "resolutions": best.get("resolutions", []),
                "fps": best.get("fps", []),
                "hdr": best.get("hdr", []),
                "color_depth": best.get("color_depth", []),
            },
            requested=requested,
        )

        return {
            "status": resolution["status"],
            "selected_model": best,
            "shot_profile": shot_profile,
            "requested_quality": resolution["requested_quality"],
            "actual_quality": resolution["actual_quality"],
            "fallback_applied": resolution["fallback_applied"],
            "notification": resolution["notification"],
            "time": datetime.now().isoformat(),
        }

    @staticmethod
    def _score_model(model, profile):
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
