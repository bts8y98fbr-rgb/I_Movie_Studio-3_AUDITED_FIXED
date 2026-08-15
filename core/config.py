from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    root_dir: Path

    @classmethod
    def from_root(cls, root_dir: Path | None = None) -> "AppConfig":
        root = (root_dir or Path(__file__).resolve().parents[1]).resolve()
        config = cls(root)
        config.ensure_directories()
        return config

    @property
    def config_dir(self) -> Path: return self.root_dir / "config"
    @property
    def data_dir(self) -> Path: return self.root_dir / "data"
    @property
    def projects_dir(self) -> Path: return self.root_dir / "projects"
    @property
    def cache_dir(self) -> Path: return self.root_dir / "cache"
    @property
    def logs_dir(self) -> Path: return self.root_dir / "logs"
    @property
    def temp_dir(self) -> Path: return self.root_dir / "temp"
    @property
    def exports_dir(self) -> Path: return self.root_dir / "exports"
    @property
    def assets_dir(self) -> Path: return self.root_dir / "assets"
    @property
    def settings_file(self) -> Path: return self.config_dir / "settings.json"
    @property
    def database_file(self) -> Path: return self.data_dir / "ai_movie_studio.db"
    @property
    def log_file(self) -> Path: return self.logs_dir / "system.log"

    def ensure_directories(self) -> None:
        for path in (
            self.config_dir, self.data_dir, self.projects_dir, self.cache_dir,
            self.logs_dir, self.temp_dir, self.exports_dir, self.assets_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
