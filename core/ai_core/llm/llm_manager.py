from core.ai_core.llm.local_llm import (
    LocalLLMProvider,
)
from core.ai_core.llm.null_llm import (
    NullLLMProvider,
)
from core.ai_core.llm.remote_llm import (
    RemoteLLMProvider,
)


class LLMManager:
    """
    Selects an LLM backend without exposing provider-specific
    implementation details to the rest of the application.
    """

    def __init__(
        self,
        runtime_policy=None,
        local_backend=None,
        remote_backend=None,
        local_model=None,
        remote_model=None,
    ):
        self.runtime_policy = runtime_policy

        self.local = LocalLLMProvider(
            backend=local_backend,
            model=local_model,
        )

        self.remote = RemoteLLMProvider(
            backend=remote_backend,
            model=remote_model,
        )

        self.none = NullLLMProvider()

    def select(self, preference="auto"):
        if preference == "never":
            return self.none

        if preference == "local":
            if self._local_allowed():
                return self.local

            return self.none

        if preference == "remote":
            if self.remote.available():
                return self.remote

            return self.none

        if self._local_allowed():
            return self.local

        if self.remote.available():
            return self.remote

        return self.none

    def generate(
        self,
        prompt,
        preference="auto",
        **kwargs,
    ):
        provider = self.select(
            preference=preference,
        )

        result = provider.generate(
            prompt,
            **kwargs,
        )

        if isinstance(result, dict):
            result.setdefault(
                "provider",
                provider.name,
            )

        return result

    def status(self):
        return {
            "local": self.local.status(),
            "remote": self.remote.status(),
            "fallback": self.none.status(),
        }

    def _local_allowed(self):
        if self.runtime_policy is None:
            return False

        return self.runtime_policy.should_use_local_llm(
            preference="auto"
        )
