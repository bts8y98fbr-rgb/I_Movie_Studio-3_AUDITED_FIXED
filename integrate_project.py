#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])

def fail(msg):
    print("ERROR:", msg)
    raise SystemExit(1)

def replace_once(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly 1 anchor, found {count} in {path}")
    path.write_text(text.replace(old, new, 1))
    print(f"OK: {label}")

p = root / "core/movie_engine/movie_pipeline.py"
if p.exists():
    text = p.read_text()

    old = """from core.ai_core.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)
"""
    new = old + """from core.ai_core.orchestration.reactive_orchestrator import (
    ReactiveOrchestrator,
)
"""
    replace_once(p, old, new, "MoviePipeline import")

    old = """        self.production_orchestrator = (
            production_orchestrator
            or ProductionOrchestrator()
        )
"""
    new = old + """        self._scene_inputs = {}
        self.reactive_orchestrator = ReactiveOrchestrator(
            submit_scene=self._regenerate_scene_from_master_prompt,
        )
"""
    replace_once(p, old, new, "MoviePipeline reactive controller")

    old = """    def create_scene(
        self,
        scene_id,
        scene_data,
        duration=5,
    ):
"""
    new = old + """        self._scene_inputs[int(scene_id)] = {
            "scene_data": dict(scene_data),
            "duration": float(duration),
        }
"""
    replace_once(p, old, new, "MoviePipeline scene registry")

    if "def regenerate_from_master_prompt(" not in text:
        start = text.find("    def create_scene(")
        marker = "\n\n    def "
        idx = text.find(marker, start + 10)
        if start < 0 or idx < 0:
            fail("MoviePipeline insertion point not found")
        methods = """
    def regenerate_from_master_prompt(
        self,
        prompt,
        affected_scene_ids=None,
    ):
        scene_ids = (
            list(self._scene_inputs)
            if affected_scene_ids is None
            else list(affected_scene_ids)
        )
        return self.reactive_orchestrator.apply(prompt, scene_ids)

    def _regenerate_scene_from_master_prompt(
        self,
        scene_id,
        prompt,
    ):
        original = self._scene_inputs.get(int(scene_id))
        if original is None:
            return {
                "status": "skipped",
                "scene_id": scene_id,
                "reason": "Scene is not registered in this pipeline",
            }

        scene_data = dict(original["scene_data"])
        scene_data["master_prompt"] = prompt
        result = self.create_scene(
            scene_id,
            scene_data,
            original["duration"],
        )
        return {
            "status": "submitted",
            "scene_id": scene_id,
            "generated_tasks": len(result.get("generated_tasks", [])),
        }
"""
        text = text[:idx] + methods + text[idx:]
        p.write_text(text)
        print("OK: MoviePipeline reactive methods")
    else:
        print("OK: MoviePipeline reactive methods already present")
else:
    print("WARN: core/movie_engine/movie_pipeline.py not found; pipeline integration skipped")

p = root / "ui/main_window.py"
if p.exists():
    text = p.read_text()
    if "def _create_generation_page(" not in text:
        old = "from core.project_manager import Project, ProjectManager\n"
        new = old + "from core.movie_engine.movie_pipeline import MoviePipeline\n"
        replace_once(p, old, new, "UI MoviePipeline import")

        old = "    QPushButton,\n"
        new = old + "    QPlainTextEdit,\n"
        replace_once(p, old, new, "UI QPlainTextEdit import")

        old = """            self.project_manager: ProjectManager | None = None
            self.current_project: Project | None = None
"""
        new = old + """            self.movie_pipeline: MoviePipeline | None = None
"""
        replace_once(p, old, new, "UI pipeline state")

        old = """        def _create_page(self, name: str) -> QWidget:
            if name == "AI Models":
                return self._create_models_page()
"""
        new = """        def _create_page(self, name: str) -> QWidget:
            if name == "AI Models":
                return self._create_models_page()
            if name == "Generation":
                return self._create_generation_page()
"""
        replace_once(p, old, new, "UI Generation page route")

        marker = "\n        def _set_current_project("
        idx = text.find(marker)
        if idx < 0:
            fail("UI insertion point not found")
        methods = """
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

"""
        text = text[:idx] + methods + text[idx:]
        p.write_text(text)
        print("OK: UI Generation page")

        if "self.movie_pipeline = MoviePipeline(project.path)" not in text:
            old = "        self.current_project = project\n"
            new = old + "        self.movie_pipeline = MoviePipeline(project.path)\n"
            replace_once(p, old, new, "UI current project pipeline")
    else:
        print("OK: UI Generation page already present")
else:
    print("WARN: ui/main_window.py not found; UI integration skipped")

print("Integration complete.")
