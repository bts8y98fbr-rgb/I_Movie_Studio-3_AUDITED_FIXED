from pathlib import Path

from core.config import AppConfig
from core.logger_manager import LoggerManager
from core.project_manager import ProjectManager
from core.settings_manager import SettingsManager
from database.database_manager import DatabaseManager


def test_config_creates_directories(tmp_path: Path):
    config = AppConfig.from_root(tmp_path)
    assert config.database_file.parent.exists()
    assert config.projects_dir.exists()


def test_settings_persist(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = SettingsManager(path, {"theme": "dark"})
    settings.set("language", "ru")
    assert SettingsManager(path).get("language") == "ru"


def test_database_schema(tmp_path: Path):
    with DatabaseManager(tmp_path / "db.sqlite") as db:
        names = {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"projects", "settings"}.issubset(names)


def test_project_lifecycle(tmp_path: Path):
    db = DatabaseManager(tmp_path / "db.sqlite")
    manager = ProjectManager(tmp_path / "projects", db)
    project = manager.create("My Movie")
    reopened = manager.open(project.path)
    assert reopened.name == "My_Movie"
    assert (project.path / "project.json").exists()
    db.close()


def test_logger_writes_file(tmp_path: Path):
    log_path = tmp_path / "logs" / "system.log"
    logger = LoggerManager.setup(log_path, f"test-{tmp_path.name}")
    logger.info("test message")
    assert log_path.exists()
    assert "test message" in log_path.read_text(encoding="utf-8")
