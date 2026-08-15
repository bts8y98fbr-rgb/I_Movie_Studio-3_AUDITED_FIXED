"""Application entry point."""
from core.config import AppConfig
from database.database_manager import DatabaseManager
from core.project_manager import ProjectManager
from ui.main_window import create_application


if __name__ == "__main__":
    config = AppConfig.from_root()
    database = DatabaseManager(config.database_file)
    project_manager = ProjectManager(config.projects_dir, database)
    app, window = create_application()
    window.set_project_manager(project_manager)
    window.show()
    try:
        raise SystemExit(app.exec())
    finally:
        database.close()
