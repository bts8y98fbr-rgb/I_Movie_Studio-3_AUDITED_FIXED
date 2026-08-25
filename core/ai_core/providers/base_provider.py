from abc import ABC, abstractmethod


class BaseAIProvider(ABC):

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def generate(self, prompt, **kwargs):
        pass

    def capabilities(self):
        """Return provider capabilities for routing and quality selection."""
        return {
            "media_types": [],
            "resolutions": [],
            "fps": [],
            "hdr": [],
            "color_depth": [],
            "audio": {
                "quality": "high",
                "channels": 2,
                "channel_layout": "stereo",
            },
        }

    def status(self):
        return {
            "provider": self.name,
            "ready": True,
            "capabilities": self.capabilities(),
        }
