# CHANGELOG

## v0.1.0

### Phase 1 — Core foundation — COMPLETE

- Added `AppConfig` for centralized application paths and automatic directory creation.
- Added `SettingsManager` with JSON persistence and atomic replacement.
- Added `DatabaseManager` with SQLite initialization and query/execute helpers.
- Added `ProjectManager` for project creation, persistence and reopening.
- Added `LoggerManager` with rotating `system.log` output and console logging.
- Added automated Phase 1 tests.
- Added a single documentation index and workflow.
- Added the future AI provider architecture decision: user-controlled model selection, provider abstraction, WaveSpeed as a first-class provider, and fixed/preferred/automatic selection policies. This is design-only in Phase 1.

### Validation

- Full Phase 1 test suite must pass before moving to Phase 2.
- No runtime WaveSpeed, Kling, PyQt6, FFmpeg or AI Director implementation is included in Phase 1.

## v0.2.0

### Phase 2 — PyQt6 desktop shell

- Added the PyQt6 `QMainWindow` application shell.
- Added stacked workspaces and project dock/status bar.
- Added AI Models workspace with user-controlled provider/model selection.
- Added `Fixed`, `Preferred` and `Automatic` model-selection policy primitives.
- Added optional GUI tests and PyQt6/pytest-qt requirements.
- Added Phase 2 architecture documentation.

### Validation

- Python source passes bytecode compilation in the build environment.
- GUI tests are dependency-gated and run when PyQt6/pytest-qt are installed.
- No real provider API calls are introduced in Phase 2.

## v0.3.0

### Phase 3 — Project Management

- Extended `ProjectManager` with atomic manifest writes.
- Added project listing and SQLite registry synchronization.
- Added timestamped project manifest backups and latest-backup restore.
- Added project UI integration for New Project, Open Project and Save Project.
- Added 60-second autosave for the active project.
- Added Phase 3 project-management tests and architecture documentation.

### Validation

- Full automated suite: 9 passed, 1 skipped.
- Python source compilation: OK.
- GUI runtime validation remains dependency/target-machine dependent.
- No real WaveSpeed, Kling, FFmpeg, voice, rendering or AI Director execution was introduced.
