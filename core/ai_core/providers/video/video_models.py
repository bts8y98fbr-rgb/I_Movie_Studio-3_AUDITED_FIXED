from dataclasses import dataclass, field


@dataclass
class VideoGenerationRequest:

    prompt: str

    quality: str = "8k"

    scene_id: int | None = None

    shot_id: int | None = None

    metadata: dict = field(
        default_factory=dict
    )


@dataclass
class VideoGenerationResponse:

    provider: str

    status: str

    job_id: str | None = None

    asset_id: str | None = None

    asset_url: str | None = None

    metadata: dict = field(
        default_factory=dict
    )
