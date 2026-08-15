# AI Movie Studio — stabilization audit

Date: 2026-08-15
Source: AI_Movie_Studio-3_CURRENT.zip

## First stabilization completed

The generation pipeline had a confirmed identity propagation bug: `GenerationEngine` created tasks without `scene_id`/`shot_id` metadata, while `VideoProvider` defaulted missing IDs to `0`. As a result, scene 1 generation could write assets under `scene_000/shot_000`.

### Changes

- `GenerationEngine` now propagates `scene_id`, `shot_id`, timeline, duration, camera, quality settings and model selection into each `GenerationTask`.
- `GenerationQueue` now forwards `project_path` and full metadata to providers.
- `GenerationQueue` now marks provider exceptions as `failed` instead of falsely reporting `done`.
- `GenerationEngine` reports `generated`, `failed`, and `completed_with_errors` accurately.
- `VideoProvider` now requires valid `scene_id` and `shot_id` metadata instead of silently defaulting to `0`.
- `VideoProvider` uses render-plan quality metadata for FPS/resolution/HDR/color depth when available.
- Added an automated regression test covering scene 1 with shots 1–3.

## Verification

`pytest`: **10 passed, 1 skipped**.

The new regression test confirms that generated assets land in:

- `assets/video/scene_001/shot_001`
- `assets/video/scene_001/shot_002`
- `assets/video/scene_001/shot_003`

and retain matching scene/shot metadata.

## Remaining architecture work

1. Consolidate the legacy `core/ai_core/video_provider.py` layer; it currently coexists with `core/ai_core/providers/video/video_provider.py`.
2. Decide on one authoritative asset persistence path; `GenerationQueue`, `AIResultStorage`, `AssetGenerator`, and `VideoProvider` currently overlap in responsibility.
3. Add end-to-end tests for RenderEngine → GenerationEngine → assets → compile → export.
4. Replace the manifest-only VideoProvider with a real external video API adapter.
5. Add real media rendering/FFmpeg assembly and audio/subtitle pipelines.
6. Keep the current project pipeline as the canonical path while removing obsolete backup/duplicate modules.
