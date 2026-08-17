from core.ai_core.providers.base_provider import BaseAIProvider


class MusicProvider(BaseAIProvider):

    def __init__(self, name="Music AI"):
        super().__init__(name)


    def capabilities(self):
        return {
            "media_types": ["music"],
            "resolutions": [],
            "fps": [],
            "hdr": [],
            "color_depth": [],
            "audio": {
                "quality": "high",
                "channels": 2,
                "channel_layout": "stereo",
            },
            "implementation": "deterministic_music_adapter",
        }

    def generate(self, prompt, **kwargs):
        return {
            "type": "music",
            "prompt": prompt,
            "status": "generated",
            "asset": None,
            "metadata": {
                "duration": None,
                "tempo": None
            }
        }
