# TASK.md

Work strictly by phase. Complete and validate the current phase before starting the next.

## Phase 1 — Core foundation

- SettingsManager
- ProjectManager
- DatabaseManager
- LoggerManager
- AppConfig
- tests
- CHANGELOG.md update

Status: **Complete**.

## Phase 2 — PyQt6 desktop shell

- QMainWindow
- QStackedWidget navigation
- QDockWidget project context
- QStatusBar
- dark theme
- AI Models workspace
- user-controlled model policy: Fixed / Preferred / Automatic
- tests
- CHANGELOG.md update

Status: **Complete pending target-machine GUI runtime check**.

## Phase 3 — Project Management

- create project
- open project
- save project
- atomic project manifest persistence
- SQLite project registry
- project listing
- timestamped backups
- restore latest backup
- UI integration for New/Open/Save
- 60-second autosave
- tests
- CHANGELOG.md update

Status: **Complete; target-machine GUI runtime check remains recommended**.

## Rules

- Do not connect real Kling, WaveSpeed, FFmpeg, voice or rendering services before their designated phases.
- The AI Director must never silently replace a user-selected model.
- Provider/model execution belongs in the provider layer, not the PyQt6 UI layer.
- Project-level AI/model policy overrides global defaults.
