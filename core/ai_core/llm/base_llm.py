from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Common interface for all LLM backends."""

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate(self, prompt, **kwargs):
        raise NotImplementedError

    def status(self):
        return {
            "name": self.name,
            "available": self.available(),
        }
