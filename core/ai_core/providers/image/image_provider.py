from core.ai_core.providers.base_provider import BaseAIProvider


class ImageProvider(BaseAIProvider):

    def __init__(self, name="Image AI"):
        super().__init__(name)


    def capabilities(self):
        return {
            "media_types": ["image"],
            "resolutions": ["1920x1080", "3840x2160", "7680x4320"],
            "fps": [],
            "hdr": [False, True],
            "color_depth": [8, 10],
            "audio": {
                "quality": "high",
                "channels": 2,
                "channel_layout": "stereo",
            },
            "implementation": "deterministic_image_adapter",
        }

    def generate(self, prompt, **kwargs):
        return {
            "type": "image",
            "prompt": prompt,
            "status": "generated",
            "asset": None,
            "metadata": {}
        }
