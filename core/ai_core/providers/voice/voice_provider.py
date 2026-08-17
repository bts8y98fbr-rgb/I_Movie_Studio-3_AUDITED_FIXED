from core.ai_core.providers.base_provider import BaseAIProvider


class VoiceProvider(BaseAIProvider):

    def __init__(self, name="Voice AI"):
        super().__init__(name)


    def capabilities(self):
        return {
            "media_types": ["voice"],
            "resolutions": [],
            "fps": [],
            "hdr": [],
            "color_depth": [],
            "audio": {
                "quality": "high",
                "channels": 2,
                "channel_layout": "stereo",
            },
            "implementation": "deterministic_voice_adapter",
        }

    def generate(self, prompt, **kwargs):
        return {
            "type": "voice",
            "prompt": prompt,
            "status": "generated",
            "asset": None,
            "metadata": {
                "duration": None,
                "language": None
            }
        }
