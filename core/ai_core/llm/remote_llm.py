from core.ai_core.llm.base_llm import BaseLLMProvider


class RemoteLLMProvider(BaseLLMProvider):
    """
    Adapter boundary for remote/cloud LLM services.

    Provider-specific API implementations belong outside this class.
    """

    def __init__(
        self,
        backend=None,
        model=None,
    ):
        super().__init__("remote")
        self.backend = backend
        self.model = model

    def available(self) -> bool:
        return self.backend is not None

    def generate(self, prompt, **kwargs):
        if not self.available():
            return {
                "status": "unavailable",
                "provider": self.name,
                "content": None,
                "reason": "No remote LLM backend configured",
            }

        return self.backend.generate(
            prompt,
            model=self.model,
            **kwargs,
        )
