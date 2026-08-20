import uuid

from .base_video_provider import BaseVideoProvider


class RemoteVideoProvider(BaseVideoProvider):
    """
    Remote AI video generation adapter.

    Real generation happens on external AI services.
    Local machine only creates and tracks generation jobs.

    Future providers:
        Sora
        Veo
        Runway
        Kling
        Pika
    """

    def __init__(
        self,
        name="remote_video_ai",
    ):
        super().__init__(name)

    def submit_generation(
        self,
        prompt,
        quality,
        metadata=None,
    ):
        job_id = str(
            uuid.uuid4()
        )[:8]

        return {
            "job_id": job_id,
            "provider": self.name,
            "status": "submitted",
            "asset_url": None,
            "prompt": prompt,
            "quality": quality,
            "metadata": metadata or {},
        }

    def generate(
        self,
        prompt,
        quality="8k",
        metadata=None,
        **kwargs,
    ):
        return self.submit_generation(
            prompt,
            quality,
            metadata,
        )

    def get_status(
        self,
        job_id,
    ):
        return {
            "job_id": job_id,
            "status": "processing",
        }
