from core.ai_core.llm.base_llm import BaseLLMProvider


class LocalLLMProvider(BaseLLMProvider):
    """
    Adapter boundary for locally running LLMs.

    Concrete backends such as Kimi, Qwen, Llama, Ollama,
    llama.cpp, etc. can be connected later without changing
    the rest of the application.
    """

    def __init__(
        self,
        backend=None,
        model=None,
    ):
        super().__init__("local")
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
                "reason": "No local LLM backend configured",
            }

        return self.backend.generate(
            prompt,
            model=self.model,
            **kwargs,
        )
