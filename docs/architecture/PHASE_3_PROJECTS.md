# Phase 3 — Project Management

Phase 3 connects the desktop shell to the core project layer without introducing provider execution.

## Responsibilities

- create and open projects;
- persist `project.json` atomically;
- register projects in SQLite;
- list existing registered projects;
- create timestamped manifest backups on save;
- restore the latest manifest backup;
- provide UI actions for new/open/save;
- autosave the active project every 60 seconds;
- keep project-level metadata available for future AI/model policy overrides.

## Boundaries

This phase does not call Kling, WaveSpeed, FFmpeg, voice services, image/video models or the AI Director.
