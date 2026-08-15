from abc import ABC, abstractmethod


class BaseAIProvider(ABC):

    def __init__(self, name):
        self.name = name


    @abstractmethod
    def generate(self, prompt, **kwargs):
        pass


    def status(self):
        return {
            "provider": self.name,
            "ready": True
        }

