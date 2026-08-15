class ScenePlanner:

    def create_plan(self, scene):

        return {
            "visual": scene.get("visual"),
            "video": scene.get("video"),
            "voice": scene.get("voice"),
            "music": scene.get("music")
        }
