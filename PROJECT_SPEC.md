# AI Movie Studio — Project Specification

## Product vision
AI Movie Studio Studio Edition is a Windows desktop application intended to automate AI-assisted film production from a user's creative brief through scripts, characters, locations, images, video, voice, sound, subtitles and final rendering.

## Architectural principles
- The application should be highly autonomous when the user enables Autonomous Mode.
- The user must retain control over providers and model selection.
- AI Director orchestrates production tasks; it must not silently replace user-selected models.
- Providers must be replaceable through an abstraction layer.
- WaveSpeed is a first-class provider because it exposes a unified API over many AI models and asynchronous prediction tasks.
- Direct provider integrations such as Kling may coexist with WaveSpeed.
- Project-level AI/model policy overrides global defaults.

## Model selection policy
- `fixed`: user-selected provider/model is mandatory.
- `preferred`: user supplies an ordered set; fallback is allowed only within that approved set.
- `automatic`: AI Director may choose only from the user's explicitly approved set.

## Phase 1
Implement and validate:
- `AppConfig`
- `SettingsManager`
- `DatabaseManager`
- `ProjectManager`
- `LoggerManager`
- tests
- documentation structure
- `CHANGELOG.md`

Later phases contain PyQt6 UI, provider integrations, Kling/WaveSpeed execution, AI Director, rendering and packaging. Those phases must not be implemented early.
