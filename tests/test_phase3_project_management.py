from __future__ import annotations

import json
from pathlib import Path

from core.project_manager import ProjectManager
from database.database_manager import DatabaseManager


def make_manager(tmp_path: Path) -> ProjectManager:
    return ProjectManager(tmp_path / "projects", DatabaseManager(tmp_path / "data" / "app.db"))


def test_create_project_builds_structure_and_registers_it(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    project = manager.create("My Test Film")

    assert project.path.name == "My_Test_Film"
    assert (project.path / "project.json").is_file()
    assert (project.path / "characters").is_dir()
    assert (project.path / "backups").is_dir()
    assert manager.database.query("SELECT name FROM projects")[0]["name"] == "My_Test_Film"


def test_save_creates_backup_and_open_round_trips_metadata(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    project = manager.create("Film")
    project.metadata = {"genre": "sci-fi", "duration_minutes": 8}
    manager.save(project, create_backup=False)
    project.metadata["genre"] = "thriller"
    manager.save(project)

    backups = list((project.path / "backups").glob("project_*.json"))
    assert backups
    reopened = manager.open(project.path)
    assert reopened.metadata["genre"] == "thriller"


def test_restore_latest_backup_restores_previous_manifest(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    project = manager.create("Film")
    project.metadata = {"version": 1}
    manager.save(project, create_backup=False)
    project.metadata = {"version": 2}
    manager.save(project)

    restored = manager.restore_latest_backup(project)
    assert restored.metadata["version"] == 1
    payload = json.loads((project.path / "project.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["version"] == 1


def test_list_projects_returns_registered_existing_projects(tmp_path: Path) -> None:
    manager = make_manager(tmp_path)
    manager.create("One")
    manager.create("Two")
    names = {project.name for project in manager.list_projects()}
    assert names == {"One", "Two"}
