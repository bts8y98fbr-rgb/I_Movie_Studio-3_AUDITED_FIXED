from datetime import datetime


class ShotModelSelector:

    def __init__(
        self,
        model_router
    ):

        self.model_router = model_router


    def select_for_shot(
        self,
        shot
    ):

        shot_type = (
            shot
            .get("camera", {})
            .get("shot_type", "")
        )


        movement = (
            shot
            .get("camera", {})
            .get("movement", "")
        )


        profile = "cinematic"


        if shot_type in [
            "wide_establishing",
            "epic_space"
        ]:

            profile = "environment"


        elif shot_type in [
            "hero_reveal",
            "medium_action"
        ]:

            profile = "motion"


        elif shot_type in [
            "cinematic_close",
            "close_detail"
        ]:

            profile = "detail"



        model_result = (
            self.model_router
            .get_best_model("video")
        )


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
                        movement

                },


            "selected_model":
                model_result

        }
