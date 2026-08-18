from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class RenderPreset:
    name: str
    resolution: str
    fps: int
    hdr: bool
    color_depth: int
    description: str


class RenderPresetManager:
    """
    Stores user-selected render targets.

    4K is the default. 8K is an explicit selectable target. Provider fallback
    is resolved by QualityPolicy, not by this class.
    """

    PRESETS = {
        "super_hd": RenderPreset(
            "Super HD", "1920x1080", 30, False, 8,
            "Standard cinematic HD",
        ),
        "4k": RenderPreset(
            "Cinema 4K", "3840x2160", 60, True, 10,
            "Production 4K HDR cinema",
        ),
        "production": RenderPreset(
            "Cinema 4K", "3840x2160", 60, True, 10,
            "Production 4K HDR cinema",
        ),
        "8k": RenderPreset(
            "Master 8K", "7680x4320", 60, True, 10,
            "Ultra cinematic 8K HDR master",
        ),
        "12k": RenderPreset(
            "Future 12K", "11520x6480", 60, True, 12,
            "Future production master",
        ),
    }

    def __init__(self, preset="4k"):
        if preset not in self.PRESETS:
            raise ValueError(f"Unknown render preset: {preset}")
        self.requested_preset = preset
        self.preset = self.PRESETS[preset]

    def get_settings(self) -> Dict:
        return {
            "name": self.preset.name,
            "resolution": self.preset.resolution,
            "fps": self.preset.fps,
            "hdr": self.preset.hdr,
            "color_depth": self.preset.color_depth,
            "description": self.preset.description,
        }

    def list_presets(self):
        return list(self.PRESETS.keys())
