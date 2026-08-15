from core.movie_engine.timeline import Timeline


class SceneBuilder:

    def __init__(self):
        self.timeline = Timeline()


    def build_scene(
        self,
        scene_id,
        duration,
        generated_assets
    ):

        media = {}

        for asset in generated_assets:

            media[asset.task_type] = {
                "provider": asset.provider.name,
                "result": asset.result
            }


        return self.timeline.add_scene(
            scene_id,
            duration,
            media
        )


    def get_movie_timeline(self):

        return self.timeline.get_timeline()
