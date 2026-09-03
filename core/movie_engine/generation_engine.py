from datetime import datetime
import json
from pathlib import Path

from core.ai_core.generation_queue import GenerationQueue, GenerationTask
from core.ai_core.provider_manager import ProviderManager
from core.ai_core.providers import ProviderCatalog, ProviderRouter, CredentialManager
from core.ai_core.quality_policy import QualityPolicy


class GenerationEngine:
    def __init__(
        self,
        project_path="projects/test_movie",
        quality="4k",
        model_policy=None,
    ):
        self.project_path = Path(project_path)
        self.quality = quality
        self.model_policy = model_policy
        self.provider_manager = ProviderManager()
        self.provider_manager.load_default_providers()
        # New provider-routing layer. The legacy ProviderManager remains
        # the execution backend until all concrete providers are migrated.
        self.provider_catalog = ProviderCatalog()
        self.provider_router = ProviderRouter(
            self.provider_catalog,
            execution_available=lambda name: (
                self.provider_manager.get(name) is not None
            ),
        )
        self.credentials = CredentialManager()
        self.quality_policy = QualityPolicy(quality)
        self.queue = GenerationQueue()

    def generate_scene(self, scene_id):
        render_plan_path = (
            self.project_path / "render"
            / f"scene_{scene_id:03d}"
            / "render_plan.json"
        )
        if not render_plan_path.exists():
            raise FileNotFoundError(render_plan_path)

        render_plan = json.loads(
            render_plan_path.read_text(encoding="utf-8")
        )
        # Route the task through the catalog and preserve that provider
        # identity at the execution boundary.
        routed_provider = self.provider_router.select("video", mode="free")

        if routed_provider is None:
            raise RuntimeError("No eligible video provider in catalog")

        routed_name = routed_provider.name
        video_provider = self.provider_manager.get(routed_name)

        if video_provider is None:
            raise RuntimeError(
                f"No execution backend available for routed provider: "
                f"{routed_name}"
            )

        self.queue = GenerationQueue()

        for shot in render_plan.get("shots", []):
            shot_id = shot.get("shot_id")
            if shot_id is None:
                raise ValueError("Render plan shot is missing shot_id")

            requested_quality = dict(
                shot.get("quality")
                or render_plan.get("render_settings")
                or self.quality_policy.get_video_defaults()
            )

            # Render presets use "name"; QualityPolicy works with the
            # capability fields only.
            requested_quality = {
                "resolution": requested_quality.get("resolution"),
                "fps": requested_quality.get("fps", 60),
                "hdr": requested_quality.get("hdr", True),
                "color_depth": requested_quality.get("color_depth", 10),
            }

            resolved = self.quality_policy.resolve_quality(
                capabilities=video_provider.capabilities(),
                requested=requested_quality,
            )

            metadata = {
                "scene_id": scene_id,
                "shot_id": shot_id,
                "timeline": shot.get("timeline", {}),
                "duration": shot.get("timeline", {}).get("duration"),
                "camera": shot.get("camera", {}),
                "quality": resolved["actual_quality"],
                "requested_quality": resolved["requested_quality"],
                "actual_quality": resolved["actual_quality"],
                "fallback_applied": resolved["fallback_applied"],
                "quality_notification": resolved["notification"],
                "shot_model_selection": shot.get(
                    "shot_model_selection", {}
                ),
            }

            task = GenerationTask(
                task_type="video",
                prompt=shot.get("director_prompt", ""),
                provider=video_provider,
                quality=self.quality,
                project_path=self.project_path,
                metadata=metadata,
                model_policy=self.model_policy,
            )
            self.queue.add_task(task)

        results = self.queue.process_all()
        failed = sum(1 for task in results if task.status == "failed")

        actual_qualities = [
            task.metadata.get("actual_quality")
            for task in results
            if task.metadata.get("actual_quality")
        ]

        output = {
            "scene_id": scene_id,
            "created": datetime.now().isoformat(),
            "quality": self.quality,
            "requested_quality": self.quality_policy.get_video_defaults(),
            "actual_quality": actual_qualities[0] if actual_qualities else None,
            "generated": sum(
                1 for task in results if task.status == "done"
            ),
            "failed": failed,
            "status": (
                "completed"
                if failed == 0
                else "completed_with_errors"
            ),
            "tasks": self.queue.get_status(),
        }

        output_path = (
            self.project_path / "render_output"
            / f"scene_{scene_id:03d}"
            / "generation_result.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return str(output_path)

    def load_result(self, scene_id):
        file = (
            self.project_path / "render_output"
            / f"scene_{scene_id:03d}"
            / "generation_result.json"
        )
        return json.loads(file.read_text(encoding="utf-8"))
