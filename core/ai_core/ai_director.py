from datetime import datetime
from pathlib import Path
import json

from core.ai_core.llm import LLMManager
from core.ai_core.runtime import RuntimePolicy


class AIDirector:
    """
    AI-assisted director.

    The director always has a deterministic local fallback.
    An LLM is an optional enhancement layer and is never required
    for the application to operate.
    """

    def __init__(
        self,
        project_path="projects/test_movie",
        quality="8k",
        llm_manager=None,
        runtime_policy=None,
        llm_preference="auto",
    ):
        self.project_path = Path(project_path)
        self.quality = quality
        self.llm_preference = llm_preference

        self.director_path = (
            self.project_path /
            "director"
        )

        self.director_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.runtime_policy = (
            runtime_policy
            or RuntimePolicy()
        )

        self.llm_manager = (
            llm_manager
            or LLMManager(
                runtime_policy=self.runtime_policy
            )
        )

    def detect_scene_type(
        self,
        scene_data,
    ):
        text = str(scene_data).lower()

        if any(
            x in text
            for x in [
                "battle",
                "fight",
                "attack",
                "war",
            ]
        ):
            return "action"

        if any(
            x in text
            for x in [
                "space",
                "station",
                "planet",
                "galaxy",
            ]
        ):
            return "epic_space"

        if any(
            x in text
            for x in [
                "dark",
                "horror",
                "fear",
            ]
        ):
            return "horror"

        if any(
            x in text
            for x in [
                "talk",
                "dialogue",
                "conversation",
            ]
        ):
            return "dialogue"

        return "cinematic"

    def build_shot(
        self,
        shot_id,
        start,
        duration,
        visual,
        action,
        scene_type,
    ):
        if scene_type == "action":
            shots = [
                (
                    "dynamic_wide",
                    "fast_tracking",
                ),
                (
                    "close_action",
                    "handheld_motion",
                ),
            ]

        elif scene_type == "epic_space":
            shots = [
                (
                    "wide_establishing",
                    "slow_orbit",
                ),
                (
                    "hero_reveal",
                    "camera_push",
                ),
                (
                    "cinematic_close",
                    "slow_tracking",
                ),
            ]

        elif scene_type == "horror":
            shots = [
                (
                    "dark_wide",
                    "slow_dolly",
                ),
                (
                    "close_tension",
                    "slow_zoom",
                ),
            ]

        elif scene_type == "dialogue":
            shots = [
                (
                    "medium_dialogue",
                    "static_camera",
                ),
                (
                    "close_emotion",
                    "slow_push",
                ),
            ]

        else:
            shots = [
                (
                    "wide_establishing",
                    "slow_tracking",
                ),
                (
                    "medium_action",
                    "camera_move",
                ),
            ]

        selected = shots[
            (shot_id - 1) % len(shots)
        ]

        shot_type, movement = selected

        prompt = (
            f"{self.quality.upper()} HDR cinematic shot, "
            f"{visual}, "
            f"{action}, "
            f"{shot_type}, "
            f"{movement}, "
            "anamorphic lens, "
            "volumetric lighting, "
            "cinematic color grading"
        )

        return {
            "shot_id": shot_id,
            "start": round(start, 2),
            "duration": round(duration, 2),
            "camera": {
                "type": "cinematic",
                "shot_type": shot_type,
                "movement": movement,
            },
            "scene_type": scene_type,
            "director_prompt": prompt,
        }

    def _build_fallback_direction(
        self,
        scene_id,
        scene_data,
        duration,
    ):
        visual = scene_data.get(
            "visual",
            "unknown environment",
        )

        action = scene_data.get(
            "video",
            "cinematic movement",
        )

        scene_type = self.detect_scene_type(
            scene_data
        )

        if scene_type == "epic_space":
            shot_count = 3
        elif duration >= 10:
            shot_count = 3
        else:
            shot_count = 2

        shot_duration = (
            float(duration) /
            shot_count
        )

        shots = []

        for i in range(shot_count):
            shots.append(
                self.build_shot(
                    i + 1,
                    i * shot_duration,
                    shot_duration,
                    visual,
                    action,
                    scene_type,
                )
            )

        return {
            "scene_id": scene_id,
            "quality": self.quality,
            "scene_type": scene_type,
            "duration": float(duration),
            "shot_count": len(shots),
            "shots": shots,
        }

    def _build_llm_prompt(
        self,
        scene_id,
        scene_data,
        duration,
    ):
        return (
            "You are the AI film director for a cinematic "
            "movie generation system.\n\n"
            f"Scene ID: {scene_id}\n"
            f"Duration: {duration} seconds\n"
            f"Quality: {self.quality}\n"
            f"Scene data: {json.dumps(scene_data, ensure_ascii=False)}\n\n"
            "Analyze the scene and improve the cinematic "
            "direction.\n"
            "Return JSON with this structure:\n"
            "{"
            '"scene_type": "cinematic", '
            '"shots": []'
            "}\n"
            "Each shot should contain:"
            "shot_id, start, duration, camera, "
            "scene_type and director_prompt.\n"
            "Do not return markdown."
        )

    def _apply_llm_direction(
        self,
        fallback,
        llm_result,
    ):
        if not isinstance(llm_result, dict):
            return fallback

        if llm_result.get("status") != "generated":
            return fallback

        content = llm_result.get("content")

        if not isinstance(content, str):
            return fallback

        try:
            data = json.loads(content)
        except (TypeError, ValueError):
            return fallback

        if not isinstance(data, dict):
            return fallback

        shots = data.get("shots")

        if not isinstance(shots, list):
            return fallback

        valid_shots = []

        for shot in shots:
            if not isinstance(shot, dict):
                continue

            if "shot_id" not in shot:
                continue

            if "director_prompt" not in shot:
                continue

            valid_shots.append(shot)

        if not valid_shots:
            return fallback

        result = dict(fallback)

        result["scene_type"] = data.get(
            "scene_type",
            fallback["scene_type"],
        )

        result["shots"] = valid_shots
        result["shot_count"] = len(valid_shots)

        return result

    def analyze_scene(
        self,
        scene_id,
        scene_data,
        duration,
    ):
        fallback = self._build_fallback_direction(
            scene_id,
            scene_data,
            duration,
        )

        llm_result = self.llm_manager.generate(
            self._build_llm_prompt(
                scene_id,
                scene_data,
                duration,
            ),
            preference=self.llm_preference,
        )

        result = self._apply_llm_direction(
            fallback,
            llm_result,
        )

        result["scene_id"] = scene_id
        result["quality"] = self.quality
        result["duration"] = float(duration)
        result["created"] = datetime.now().isoformat()

        result["llm"] = {
            "provider": llm_result.get(
                "provider",
                "none",
            ),
            "status": llm_result.get(
                "status",
                "unavailable",
            ),
        }

        file_path = (
            self.director_path /
            f"scene_{scene_id:03d}_director.json"
        )

        with open(
            file_path,
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                result,
                f,
                indent=2,
                ensure_ascii=False,
            )

        return str(file_path)

    def load_direction(
        self,
        scene_id,
    ):
        file_path = (
            self.director_path /
            f"scene_{scene_id:03d}_director.json"
        )

        if not file_path.exists():
            return None

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)
