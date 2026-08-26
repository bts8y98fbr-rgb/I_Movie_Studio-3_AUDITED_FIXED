"""Reactive production orchestration for prompt-driven movie generation.

The master creative prompt is treated as a source-of-truth revision. A prompt
change invalidates only the selected downstream scenes and immediately submits
fresh work through the existing MoviePipeline/provider stack.
"""

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Callable, Optional


@dataclass(frozen=True)
class PromptRevision:
    revision: int
    prompt: str
    fingerprint: str
    created: str


@dataclass
class ReactiveGenerationState:
    revision: int = 0
    status: str = "idle"
    affected_scene_ids: list[int] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    last_error: Optional[str] = None


class ReactiveOrchestrator:
    """Coordinates instant prompt-driven re-planning without owning providers."""

    def __init__(self, submit_scene: Callable[[int, str], dict] | None = None):
        self.submit_scene = submit_scene
        self.history: list[PromptRevision] = []
        self.state = ReactiveGenerationState()

    @staticmethod
    def fingerprint(prompt: str) -> str:
        return sha256(prompt.strip().encode("utf-8")).hexdigest()[:16]

    def apply(self, prompt: str, affected_scene_ids: list[int]) -> dict:
        prompt = str(prompt or "").strip()
        if not prompt:
            raise ValueError("Master prompt must not be empty")

        revision = PromptRevision(
            revision=len(self.history) + 1,
            prompt=prompt,
            fingerprint=self.fingerprint(prompt),
            created=datetime.now().isoformat(),
        )
        self.history.append(revision)
        self.state = ReactiveGenerationState(
            revision=revision.revision,
            status="replanning",
            affected_scene_ids=sorted({int(x) for x in affected_scene_ids}),
        )

        try:
            for scene_id in self.state.affected_scene_ids:
                job = {
                    "revision": revision.revision,
                    "scene_id": scene_id,
                    "prompt_fingerprint": revision.fingerprint,
                    "status": "queued",
                }
                if self.submit_scene is not None:
                    result = self.submit_scene(scene_id, prompt)
                    if isinstance(result, dict):
                        job.update(result)
                self.state.jobs.append(job)

            self.state.status = "submitted" if self.state.jobs else "planned"
        except Exception as exc:
            self.state.status = "failed"
            self.state.last_error = str(exc)

        return self.snapshot()

    def snapshot(self) -> dict:
        return {
            "revision": self.state.revision,
            "status": self.state.status,
            "affected_scene_ids": list(self.state.affected_scene_ids),
            "jobs": [dict(job) for job in self.state.jobs],
            "last_error": self.state.last_error,
            "prompt_fingerprint": self.history[-1].fingerprint if self.history else None,
        }
