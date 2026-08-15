# Phase 2 — PyQt6 UI

## Scope

Phase 2 establishes the desktop shell. It does not call WaveSpeed, Kling, FFmpeg, or any other provider.

## Architecture rules

- The UI presents workspaces through `QMainWindow` + `QStackedWidget`.
- Project context is exposed through a `QDockWidget`.
- Runtime state is shown through `QStatusBar`.
- AI model choice belongs to the user.
- `Fixed`, `Preferred`, and `Automatic` selection modes are represented by `ModelPolicy`.
- Provider/model execution is deliberately outside the UI layer and will be implemented later.
