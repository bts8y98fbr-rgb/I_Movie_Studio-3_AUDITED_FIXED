# AI Provider Architecture

## Status
Design decision for the product architecture. Implementation belongs to the later AI/provider phases and is intentionally not activated in Phase 1.

## Principles
1. The user owns model selection.
2. AI Director decides *what* needs to be generated, not *which model* to use, unless the user explicitly enables automatic model selection.
3. Providers are abstracted behind a provider layer.
4. WaveSpeed is a first-class provider, not a hard-coded model list.
5. Direct providers such as Kling can coexist with WaveSpeed.
6. Model catalogs are discovered dynamically where the provider supports it.
7. Project-level model policy overrides global defaults.
8. Fixed mode forbids automatic model substitution.
9. Preferred mode permits fallback only within the user-approved model set.
10. Automatic mode may optimize within the user-approved provider/model set.

## Selection modes
- `fixed`: exactly one selected model; no substitution.
- `preferred`: ordered approved models; fallback allowed by policy.
- `automatic`: AI may select among explicitly approved models.

## Planned flow
`User request -> AI Director -> production plan -> model policy -> ProviderManager -> provider -> task queue -> result -> quality control -> render`

WaveSpeed uses asynchronous prediction tasks: submit a model request, receive a task ID, then retrieve/poll the result; webhooks can be used for production callbacks. See the official API documentation linked in project notes.
