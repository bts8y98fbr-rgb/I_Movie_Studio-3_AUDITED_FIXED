from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database.database_manager import DatabaseManager


PROJECT_FOLDERS = (
    "scenes",
    "characters",
    "locations",
    "storyboard",
    "media",
    "exports",
    "backups",
)


@dataclass
class Project:
    name: str
    path: Path
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ProjectManager:
    """Create, persist, reopen and back up movie projects."""

    def __init__(self, projects_dir: Path, database: DatabaseManager) -> None:
        self.projects_dir = Path(projects_dir)
        self.database = database
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _safe_name(name: str) -> str:
        clean = "_".join(name.strip().split())
        if not clean:
            raise ValueError("Project name cannot be empty")
        return clean

    def create(self, name: str) -> Project:
        clean = self._safe_name(name)
        path = self.projects_dir / clean
        path.mkdir(parents=True, exist_ok=False)
        for folder in PROJECT_FOLDERS:
            (path / folder).mkdir()
        now = self._now()
        project = Project(clean, path, now, now)
        self.save(project, create_backup=False)
        self.database.execute(
            "INSERT INTO projects(name, path, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (project.name, str(project.path), project.created_at, project.updated_at),
        )
        return project

    def save(self, project: Project, *, create_backup: bool = True) -> None:
        project.updated_at = self._now()
        payload = {
            "name": project.name,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "metadata": project.metadata,
        }
        target = project.path / "project.json"
        if create_backup and target.exists():
            self.backup(project)
        self._atomic_json_write(target, payload)
        self.database.execute(
            "UPDATE projects SET name = ?, updated_at = ? WHERE path = ?",
            (project.name, project.updated_at, str(project.path)),
        )

    @staticmethod
    def _atomic_json_write(target: Path, payload: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".project-", suffix=".json", dir=target.parent)
        try:
            with open(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
            Path(temp_name).replace(target)
        except Exception:
            Path(temp_name).unlink(missing_ok=True)
            raise

    def open(self, path: Path) -> Project:
        project_path = Path(path)
        manifest = project_path / "project.json"
        if not manifest.is_file():
            raise FileNotFoundError(f"Project manifest not found: {manifest}")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        project = Project(
            payload["name"],
            project_path,
            payload["created_at"],
            payload["updated_at"],
            payload.get("metadata", {}),
        )
        self.database.execute(
            "INSERT OR IGNORE INTO projects(name, path, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (project.name, str(project.path), project.created_at, project.updated_at),
        )
        return project

    def list_projects(self) -> list[Project]:
        rows = self.database.query("SELECT name, path, created_at, updated_at FROM projects ORDER BY updated_at DESC")
        projects: list[Project] = []
        for row in rows:
            path = Path(row["path"])
            if (path / "project.json").is_file():
                projects.append(self.open(path))
        return projects

    def backup(self, project: Project) -> Path:
        source = project.path / "project.json"
        if not source.exists():
            raise FileNotFoundError(source)
        backup_dir = project.path / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = backup_dir / f"project_{stamp}.json"
        if target.exists():
            target = backup_dir / f"project_{stamp}_{datetime.now().microsecond:06d}.json"
        shutil.copy2(source, target)
        return target

    def restore_latest_backup(self, project: Project) -> Project:
        backups = sorted((project.path / "backups").glob("project_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups:
            raise FileNotFoundError("No project backups available")
        payload = json.loads(backups[0].read_text(encoding="utf-8"))
        project.created_at = payload["created_at"]
        project.updated_at = payload["updated_at"]
        project.metadata = payload.get("metadata", {})
        self._atomic_json_write(project.path / "project.json", payload)
        return project
