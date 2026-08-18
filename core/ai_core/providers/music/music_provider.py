from core.ai_core.providers.base_provider import BaseAIProvider


class MusicProvider(BaseAIProvider):
    """
    Audio provider with stereo default and DTS 9.1 system ceiling.
    """

    AUDIO_FORMATS = ["stereo", "5.1", "7.1", "dts_9.1"]

    def __init__(self, name="Music AI"):
        super().__init__(name)

    def capabilities(self):
        return {
            "formats": list(self.AUDIO_FORMATS),
            "max_format": "dts_9.1",
        }

    def generate(self, prompt, **kwargs):
        requested = kwargs.get("requested_audio") or {
            "format": "stereo",
            "channels": 2,
            "channel_layout": "stereo",
        }
        actual = kwargs.get("actual_audio") or requested

        return {
            "type": "music",
            "prompt": prompt,
            "status": "generated",
            "asset": None,
            "metadata": {
                "duration": None,
                "tempo": None,
                "requested_audio": requested,
                "actual_audio": actual,
                "fallback_applied": kwargs.get("fallback_applied", False),
                "audio_notification": kwargs.get("audio_notification"),
            },
        }
