from datetime import datetime


class ShotModelSelector:

    def __init__(
        self,
        model_router,
    ):
        self.model_router = model_router


    def select_for_shot(
        self,
        shot,
    ):

        camera = shot.get(
            "camera",
            {},
        )


        shot_type = camera.get(
            "shot_type",
            "",
        )


        movement = camera.get(
            "movement",
            "",
        )


        profile = self._resolve_profile(
            shot_type,
        )


        shot_context = {

            "shot_type": shot_type,

            "movement": movement,

            "profile": profile,

            "camera": camera,

        }


        model_result = (
            self.model_router
            .get_best_model(
                "video",
                shot_context=shot_context,
            )
        )


        selected_model = dict(
            model_result["selected_model"]
        )


        requested_quality = model_result.get(
            "requested_quality"
        )
        if isinstance(requested_quality, dict):
            requested_quality = dict(requested_quality)


        actual_quality = model_result.get(
            "actual_quality"
        )
        if isinstance(actual_quality, dict):
            actual_quality = dict(actual_quality)


        routing_diagnostics = {

            "status":
                model_result.get("status"),


            "requested_quality":
                requested_quality,


            "actual_quality":
                actual_quality,


            "fallback_applied":
                model_result.get("fallback_applied"),


            "notification":
                model_result.get("notification"),


            "time":
                model_result.get("time"),

        }


        return {

            "time":
                datetime.now().isoformat(),


            "shot_profile":
                profile,


            "camera":
                {

                    "shot_type":
                        shot_type,

                    "movement":
                        movement,

                },


            "shot_context":
                shot_context,


            "selected_model":
                selected_model,


            "routing_diagnostics":
                routing_diagnostics,

        }



    @staticmethod
    def _resolve_profile(
        shot_type,
    ):

        if shot_type in [
            "wide_establishing",
            "epic_space",
        ]:
            return "environment"


        if shot_type in [
            "hero_reveal",
            "medium_action",
        ]:
            return "motion"


        if shot_type in [
            "cinematic_close",
            "close_detail",
        ]:
            return "detail"


        return "cinematic"
