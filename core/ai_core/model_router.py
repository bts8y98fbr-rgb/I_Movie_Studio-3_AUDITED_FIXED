from datetime import datetime


class ModelRouter:


    def __init__(
        self,
        quality_policy
    ):

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
                    "hdr": True
                },


                {
                    "name": "cinematic_video_pro",
                    "type": "video",
                    "quality": 8,
                    "motion": 9,
                    "realism": 8,
                    "min_resolution": "3840x2160",
                    "hdr": True
                }

            ],


            "image": [

                {
                    "name": "image_master",
                    "type": "image",
                    "quality": 10,
                    "realism": 10,
                    "hdr": True
                }

            ]

        }



    def get_best_model(
        self,
        media_type="video"
    ):


        profile = (
            self.quality_policy.get_profile()
        )


        available = self.models.get(
            media_type,
            []
        )


        approved = []


        for model in available:


            if profile["hdr"] and not model["hdr"]:

                continue


            if media_type == "video":

                if model["min_resolution"] != profile["resolution"]:

                    continue


            approved.append(model)



        if not approved:

            return {

                "status": "error",

                "message":
                    "No model satisfies quality requirements"

            }



        best = sorted(
            approved,
            key=lambda x:
                (
                    x["quality"],
                    x["realism"],
                    x.get("motion",0)
                ),
            reverse=True
        )[0]



        return {

            "status":
                "selected",


            "selected_model":
                best,


            "time":
                datetime.now().isoformat()

        }
