from core.ai_core.providers.base_provider import BaseAIProvider


class VoiceProvider(BaseAIProvider):

    def __init__(self, name="Voice AI"):
        super().__init__(name)


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
