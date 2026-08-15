from core.ai_core.providers.base_provider import BaseAIProvider


class ImageProvider(BaseAIProvider):

    def __init__(self, name="Image AI"):
        super().__init__(name)


    def generate(self, prompt, **kwargs):
        return {
            "type": "image",
            "prompt": prompt,
            "status": "generated",
            "asset": None,
            "metadata": {}
        }
