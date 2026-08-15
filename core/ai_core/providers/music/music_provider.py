from core.ai_core.providers.base_provider import BaseAIProvider


class MusicProvider(BaseAIProvider):

    def __init__(self, name="Music AI"):
        super().__init__(name)


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
