from core.ai_core.llm.base_llm import BaseLLMProvider


class NullLLMProvider(BaseLLMProvider):
    """No-op LLM backend used when no LLM is available."""

    def __init__(self):
        super().__init__("none")

    def available(self) -> bool:
        return True

    def generate(self, prompt, **kwargs):
        return {
            "status": "unavailable",
            "provider": self.name,
            "content": None,
            "reason": "No LLM backend configured",
        }
