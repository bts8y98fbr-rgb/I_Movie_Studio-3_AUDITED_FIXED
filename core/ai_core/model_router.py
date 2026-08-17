from datetime import datetime
from typing import Any


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
                    "min_resolution": "7680x4320",
                    "resolutions": ["7680x4320", "3840x2160"],
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
                    "min_resolution": "3840x2160",
                    "resolutions": ["3840x2160", "1920x1080"],
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
                "message": f"No models available for media type: {media_type}",
            }

        candidates = []

        for model in available:
            if profile["hdr"] and not self._supports_hdr(model):
                continue

            candidates.append(model)

        if not candidates:
            return {
                "status": "error",
                "message": "No model supports the required HDR capability",
            }

        best = sorted(
            candidates,
            key=lambda model: (
                model.get("quality", 0),
                model.get("realism", 0),
                model.get("motion", 0),
            ),
            reverse=True,
        )[0]

        quality_resolution = self._resolve_model_quality(best, profile)

        return {
            "status": quality_resolution["status"],
            "selected_model": best,
            "requested_quality": quality_resolution["requested_quality"],
            "actual_quality": quality_resolution["actual_quality"],
            "fallback_applied": quality_resolution["fallback_applied"],
            "notification": quality_resolution["notification"],
            "time": datetime.now().isoformat(),
        }

    def _resolve_model_quality(self, model, profile):
        capabilities = {
            "resolutions": model.get("resolutions", []),
            "fps": model.get("fps", []),
            "hdr": model.get(
                "hdr",
                [model.get("hdr", False)]
                if isinstance(model.get("hdr"), bool)
                else [],
            ),
            "color_depth": model.get("color_depth", []),
        }

        # Backward compatibility with old model definitions.
        if not capabilities["resolutions"]:
            min_resolution = model.get("min_resolution")

            if min_resolution:
                capabilities["resolutions"] = [min_resolution]

        if not capabilities["fps"]:
            capabilities["fps"] = [profile["fps"]]

        if not capabilities["color_depth"]:
            capabilities["color_depth"] = [profile["color_depth"]]

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
    def _supports_hdr(model) -> bool:
        hdr = model.get("hdr", False)

        if isinstance(hdr, list):
            return True in hdr

        return bool(hdr)
