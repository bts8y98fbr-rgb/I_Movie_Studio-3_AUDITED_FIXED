from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderDefinition:
    name: str
    media_types: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)

    api_available: bool = False
    requires_key: bool = True

    free_api: bool = False
    free_credits: bool = False

    commercial_use: bool | None = None

    quality_score: float = 0.0
    speed_score: float = 0.0

    limits: dict[str, Any] = field(default_factory=dict)
    regions: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    status: str = "unknown"

    def supports(self, media_type: str) -> bool:
        return media_type in self.media_types
