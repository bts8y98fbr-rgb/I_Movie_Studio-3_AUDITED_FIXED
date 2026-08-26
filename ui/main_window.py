"""Main application window for AI Movie Studio.

The UI deliberately separates navigation/presentation from provider execution.
Model selection is user-controlled through ModelPolicy; no provider is called here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

from core.project_manager import Project, ProjectManager
from core.movie_engine.movie_pipeline import MoviePipeline

try:
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QDockWidget,
        QFrame,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QPushButton,
        QInputDialog,
        QStackedWidget,
        QStatusBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover - allows core tooling without GUI deps
    QApplication = None  # type: ignore[assignment]


class SelectionMode(str, Enum):
    """Controls how a model may be selected for a production task."""

    FIXED = "fixed"
    PREFERRED = "preferred"
    AUTOMATIC = "automatic"


@dataclass(slots=True)
class ModelPolicy:
    """User-owned model policy; the AI Director must respect these values."""

    provider: str = "WaveSpeed"
    model: str = ""
    mode: SelectionMode = SelectionMode.FIXED

    def allows(self, provider: str, model: str) -> bool:
        if self.provider != provider:
            return False
        if self.mode is SelectionMode.FIXED:
            return model == self.model
        return True


NAVIGATION: Final[tuple[str, ...]] = (
    "Project",
    "Script",
    "Characters",
    "Locations",
    "Storyboard",
    "Generation",
    "Voice",
    "Subtitles",
    "Editing",
    "Export",
    "AI Models",
    "Settings",
)


if QApplication is not None:

    class MainWindow(QMainWindow):
        """Primary desktop window for the studio."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("AI Movie Studio — Studio Edition")
            self.resize(1400, 850)
            self.model_policies: dict[str, ModelPolicy] = {}
            self.project_manager: ProjectManager | None = None
            self.current_project: Project | None = None
            self._build_ui()
            self._autosave_timer = QTimer(self)
            self._autosave_timer.setInterval(60_000)
            self._autosave_timer.timeout.connect(self._autosave)
            self._autosave_timer.start()
            self._apply_dark_theme()

        def _build_ui(self) -> None:
            self.navigation = QListWidget()
            self.navigation.setObjectName("navigationList")
            for name in NAVIGATION:
                self.navigation.addItem(QListWidgetItem(name))

            self.pages = QStackedWidget()
            self.pages.setObjectName("pageStack")
            self.page_widgets: dict[str, QWidget] = {}
            for name in NAVIGATION:
                page = self._create_page(name)
                self.page_widgets[name] = page
                self.pages.addWidget(page)

            self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
            self.navigation.setCurrentRow(0)

            central = QWidget()
            layout = QHBoxLayout(central)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.navigation, 0)
            layout.addWidget(self.pages, 1)
            self.setCentralWidget(central)

            self.project_dock = QDockWidget("Current Project", self)
            self.project_dock.setObjectName("projectDock")
            self.project_dock.setWidget(self._project_dock_content())
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.project_dock)

            self.setStatusBar(QStatusBar(self))
            self.statusBar().showMessage("Ready")

        def _create_page(self, name: str) -> QWidget:
            if name == "AI Models":
                return self._create_models_page()

            page = QWidget()
            layout = QVBoxLayout(page)
            title = QLabel(name)
            title.setObjectName("pageTitle")
            layout.addWidget(title)
            description = QLabel(self._description_for(name))
            description.setWordWrap(True)
            layout.addWidget(description)
            layout.addStretch()
            return page

        def _create_models_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            title = QLabel("AI Models")
            title.setObjectName("pageTitle")
            layout.addWidget(title)
            layout.addWidget(QLabel("Choose which provider and model the production pipeline may use. "
                                    "The AI Director cannot override Fixed policies."))

            self.model_type = QComboBox()
            self.model_type.addItems(["Image", "Video", "Audio", "LLM"])
            self.provider = QComboBox()
            self.provider.addItems(["WaveSpeed", "Direct API"])
            self.model = QComboBox()
            self.model.setEditable(True)
            self.model.setPlaceholderText("Enter or sync a model ID")
            self.mode = QComboBox()
            self.mode.addItems(["Fixed", "Preferred", "Automatic"])

            for label, widget in (
                ("Task type", self.model_type),
                ("Provider", self.provider),
                ("Model", self.model),
                ("Selection mode", self.mode),
            ):
                row = QHBoxLayout()
                row.addWidget(QLabel(label))
                row.addWidget(widget, 1)
                layout.addLayout(row)

            self.sync_models_button = QPushButton("Sync model catalog")
            self.sync_models_button.clicked.connect(
                lambda: self.statusBar().showMessage("Model catalog sync is not connected yet")
            )
            layout.addWidget(self.sync_models_button)
            layout.addStretch()
            return page

        def _project_dock_content(self) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            label = QLabel("No project opened")
            label.setObjectName("projectLabel")
            self._project_label = label
            layout.addWidget(label)
            new_button = QPushButton("New Project")
            new_button.clicked.connect(self._new_project)
            open_button = QPushButton("Open Project")
            open_button.clicked.connect(self._open_project)
            save_button = QPushButton("Save Project")
            save_button.clicked.connect(self._save_project)
            layout.addWidget(new_button)
            layout.addWidget(open_button)
            layout.addWidget(save_button)
            layout.addStretch()
            return widget


        def set_project_manager(self, manager: ProjectManager) -> None:
            self.project_manager = manager

        def _create_generation_page(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            title = QLabel("Generation")
            title.setObjectName("pageTitle")
            layout.addWidget(title)
            layout.addWidget(QLabel(
                "Master prompt: changing it creates a new revision and "
                "regenerates only the selected/known scenes."
            ))
            self.master_prompt = QPlainTextEdit()
            self.master_prompt.setPlaceholderText(
                "Global cinematic direction..."
            )
            self.master_prompt.setMinimumHeight(150)
            layout.addWidget(self.master_prompt)
            self.regenerate_button = QPushButton(
                "Apply prompt and regenerate"
            )
            self.regenerate_button.clicked.connect(self._apply_master_prompt)
            layout.addWidget(self.regenerate_button)
            self.generation_revision_label = QLabel("Revision: —")
            self.generation_status_label = QLabel("Status: idle")
            layout.addWidget(self.generation_revision_label)
            layout.addWidget(self.generation_status_label)
            layout.addStretch()
            return page

        def _apply_master_prompt(self) -> None:
            if self.movie_pipeline is None:
                self.statusBar().showMessage("No movie pipeline is attached")
                return
            prompt = self.master_prompt.toPlainText().strip()
            if not prompt:
                self.statusBar().showMessage("Master prompt is empty")
                return
            result = self.movie_pipeline.regenerate_from_master_prompt(prompt)
            self.generation_revision_label.setText(
                f"Revision: {result.get('revision', '—')}"
            )
            self.generation_status_label.setText(
                f"Status: {result.get('status', 'unknown')}"
            )


        def _set_current_project(self, project: Project) -> None:
            self.current_project = project
            self.movie_pipeline = MoviePipeline(project.path)
            self._project_label.setText(project.name)
            self.statusBar().showMessage(f"Project opened: {project.name}")

        def _new_project(self) -> None:
            if self.project_manager is None:
                self.statusBar().showMessage("Project manager is not configured")
                return
            name, accepted = QInputDialog.getText(self, "New Project", "Project name:")
            if accepted and name.strip():
                try:
                    self._set_current_project(self.project_manager.create(name))
                except (FileExistsError, ValueError) as exc:
                    self.statusBar().showMessage(str(exc))

        def _open_project(self) -> None:
            if self.project_manager is None:
                self.statusBar().showMessage("Project manager is not configured")
                return
            path = QFileDialog.getExistingDirectory(self, "Open Project", str(self.project_manager.projects_dir))
            if path:
                try:
                    self._set_current_project(self.project_manager.open(Path(path)))
                except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
                    self.statusBar().showMessage(f"Cannot open project: {exc}")

        def _save_project(self) -> None:
            if self.project_manager is None or self.current_project is None:
                self.statusBar().showMessage("No project opened")
                return
            self.project_manager.save(self.current_project)
            self.statusBar().showMessage(f"Project saved: {self.current_project.name}")

        def _autosave(self) -> None:
            if self.project_manager is not None and self.current_project is not None:
                self.project_manager.save(self.current_project)
                self.statusBar().showMessage(f"Autosaved: {self.current_project.name}")

        @staticmethod
        def _description_for(name: str) -> str:
            descriptions = {
                "Project": "Create, open, save and manage movie projects.",
                "Script": "Develop the screenplay and scene structure.",
                "Characters": "Define characters and maintain visual identity references.",
                "Locations": "Define locations and maintain visual continuity.",
                "Storyboard": "Plan scenes, shots, camera instructions and references.",
                "Generation": "Queue and monitor AI image and video generation tasks.",
                "Voice": "Manage character voices, dialogue and narration.",
                "Subtitles": "Create, edit and synchronize subtitles.",
                "Editing": "Assemble generated assets into the final timeline.",
                "Export": "Render and export the finished movie.",
                "Settings": "Application and project configuration.",
            }
            return descriptions.get(name, "Studio workspace.")

        def _apply_dark_theme(self) -> None:
            self.setStyleSheet(
                """
                QMainWindow, QWidget { background: #181a1f; color: #e7e9ee; }
                QListWidget { background: #111318; border: 0; padding: 8px; }
                QListWidget::item { padding: 10px 12px; border-radius: 6px; }
                QListWidget::item:selected { background: #30343d; }
                QDockWidget { titlebar-close-icon: none; }
                QDockWidget::title { background: #20232a; padding: 8px; }
                QComboBox, QPushButton { background: #252932; border: 1px solid #3a3f49; padding: 7px; }
                QLabel#pageTitle { font-size: 26px; font-weight: 600; }
                QLabel#projectLabel { font-weight: 600; }
                """
            )

else:

    class MainWindow:  # pragma: no cover - dependency guard
        def __init__(self) -> None:
            raise RuntimeError("PyQt6 is required to run the desktop UI")


def create_application(argv: list[str] | None = None):
    """Create the Qt application and main window."""
    if QApplication is None:
        raise RuntimeError("PyQt6 is required to run AI Movie Studio")
    app = QApplication(argv or [])
    window = MainWindow()
    return app, window
