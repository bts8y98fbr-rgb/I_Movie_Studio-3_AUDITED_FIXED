from dataclasses import dataclass
from typing import Dict


@dataclass
class RenderPreset:

    name: str
    resolution: str
    fps: int
    hdr: bool
    color_depth: int
    description: str


class RenderPresetManager:


    PRESETS = {

        "super_hd": RenderPreset(
            name="Super HD",
            resolution="1920x1080",
            fps=30,
            hdr=False,
            color_depth=8,
            description="Standard cinematic HD"
        ),


        "4k": RenderPreset(
            name="Cinema 4K",
            resolution="3840x2160",
            fps=60,
            hdr=True,
            color_depth=10,
            description="Professional 4K HDR cinema"
        ),


        "8k": RenderPreset(
            name="Master 8K",
            resolution="7680x4320",
            fps=60,
            hdr=True,
            color_depth=10,
            description="Ultra cinematic 8K HDR master"
        ),


        "12k": RenderPreset(
            name="Future 12K",
            resolution="11520x6480",
            fps=60,
            hdr=True,
            color_depth=12,
            description="Future production master"
        )

    }


    def __init__(self, preset="8k"):

        if preset not in self.PRESETS:
            raise ValueError(
                f"Unknown render preset: {preset}"
            )

        self.preset = self.PRESETS[preset]


    def get_settings(self) -> Dict:

        return {

            "name": self.preset.name,
            "resolution": self.preset.resolution,
            "fps": self.preset.fps,
            "hdr": self.preset.hdr,
            "color_depth": self.preset.color_depth,
            "description": self.preset.description

        }


    def list_presets(self):

        return list(
            self.PRESETS.keys()
        )
