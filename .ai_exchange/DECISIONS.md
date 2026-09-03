# AI Council Decision Log

Only decisions explicitly approved by Sergey are recorded as `APPROVED`.

## Proposed decisions awaiting Sergey

## Approved standing decisions

### DEC-APPROVED-012 — GenerationEngine fixed ModelPolicy propagation RED test

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Base commit: `9d293b9`
- Related decision: `DEC-APPROVED-011`
- Related audit: `CODEX-RUN-20260903-006`
- Authorized stage: 2C — one hermetic RED test proving fixed ModelPolicy propagation through GenerationEngine
- Permitted test file only:
  - `tests/test_generation_engine_model_policy_propagation.py`
- Permitted governance worklog:
  - `.ai_exchange/CODEX_WORKLOG.md`
- Production code and existing tests must not be changed
- The test must use:
  - canonical `core.ai_core.model_policy.ModelPolicy`;
  - `SelectionMode.FIXED`;
  - actual `GenerationEngine`;
  - actual `GenerationTask`;
  - actual `GenerationQueue`
- The canonical policy may be attached to the GenerationEngine instance as the proposed propagation boundary
- The render plan must contain one shot using the flat execution-boundary schema:
  - `shot_model_selection["selected_model"]["name"]`
- A deliberate fixed model mismatch must be used
- Instance-local routing to the already registered `Video AI` backend is permitted because provider routing is not the subject of this test
- A local spy may observe calls to the registered execution backend
- `ProviderManager` and `ProviderRegistry` must not be replaced
- Expected contract:
  - the created task carries the identical canonical policy object;
  - the mismatch is refused by `GenerationQueue`;
  - `provider.generate()` receives zero calls
- Expected RED:
  - `GenerationEngine` omits `model_policy` while creating `GenerationTask`;
  - the task receives `None`;
  - provider generation is called instead of being refused
- Stop after the expected RED
- Do not run the full regression suite during the RED stage
- UI, persistence, MoviePipeline, ModelPolicy semantics, selected-model schema normalization, Router, Registry, ProviderManager, PixVerse, fallback and Reactive Orchestrator are outside scope
- Network, live APIs, credentials, `.env` and GUI are prohibited
- Existing unrelated dirty-working-tree changes must remain untouched
- Any production fix requires a separate Product Owner decision

### DEC-APPROVED-011 — Minimal fixed ModelPolicy execution-boundary production fix

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Base commit: `166f8f1`
- Related decision: `DEC-APPROVED-010`
- Authorized stage: 2B — minimal fixed ModelPolicy execution-boundary production fix
- Permitted runtime files only:
  - `core/ai_core/generation_queue.py`
  - `tests/test_runtime_model_policy_boundary.py`
- `GenerationTask` may accept an optional canonical `model_policy`
- Canonical `SelectionMode.FIXED` must be validated in `GenerationQueue.process_next()` before the `model_selection` audit and before `provider.generate()`
- Runtime provider identity must be read from `task.provider.name`
- Runtime model identity must be read as a string from `selected_model["name"]`
- Both identities must exactly match the provider and model specified by the fixed policy
- A mismatch or missing string identity must:
  - finish the task with status `failed`;
  - produce an explicit policy error;
  - prevent the `model_selection` audit;
  - prevent every call to `provider.generate()`
- An exact fixed provider/model match must permit exactly one provider call
- Tasks without `model_policy` must preserve their previous behavior
- Preferred and automatic ModelPolicy semantics must not be changed
- UI, persistence, Router, ProviderManager, ProviderRegistry, PixVerse, fallback, Reactive Orchestrator and existing tests are outside scope
- New provider integrations and fallback are prohibited
- Targeted GREEN gate: exactly `2 passed`
- Full regression gate: exactly `80 passed`, with no failures, skips or xfails
- `git diff --check` must report no errors
- The runtime commit must contain only the two permitted runtime files
- Governance records, Copilot messages, documentation and unrelated local changes must not enter the runtime commit
- Commit/push is permitted only after this decision is recorded separately in `.ai_exchange/DECISIONS.md`

### DEC-APPROVED-010 — Fixed ModelPolicy execution-boundary RED test

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Base commit: `49e6baf`
- Related decision: `DEC-APPROVED-009`
- Authorized stage: 2A — one hermetic RED test for fixed ModelPolicy enforcement at the shared generation execution boundary
- Permitted test file: `tests/test_runtime_model_policy_boundary.py`
- Permitted governance worklog: `.ai_exchange/CODEX_WORKLOG.md`
- The test must use the actual `GenerationTask` and `GenerationQueue`
- The test must use the canonical `core.ai_core.model_policy.ModelPolicy` with `SelectionMode.FIXED`
- A spy provider may be used only to observe whether `generate()` was called; network and real providers are prohibited
- The fixed policy must request one provider/model identity while the task presents a different provider/model identity
- The test must require explicit refusal before `provider.generate()` is called
- The policy may be attached to the task as the proposed explicit `task.model_policy` execution-boundary contract without changing production APIs in this RED stage
- Production code and existing tests must not be changed
- UI ModelPolicy, project persistence, preferred/automatic semantics, fallback, PixVerse, Provider Registry and Reactive Orchestrator are outside scope
- Stop after the expected RED
- A production fix requires a separate Product Owner decision

### DEC-APPROVED-009 — Stage 1E routing execution eligibility contract fix

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Base commit: `403bb4d`
- Related decision: `DEC-APPROVED-008`
- Related Copilot review: `MSG-COPILOT-20260903-005`
- Related Codex analysis: `CODEX-RUN-20260903-003`
- Authorized stage: 1E — filter catalog candidates without registered execution backends before Router scoring
- Permitted production files only:
  - `core/ai_core/providers/provider_router.py`
  - `core/movie_engine/generation_engine.py`
- Permitted test file only:
  - `tests/test_default_provider_routing_registry_consistency.py`
- `ProviderRouter` may receive an optional read-only execution-availability predicate keyed by stable provider identity
- When supplied, the predicate is a hard eligibility filter and must run before soft scoring
- `GenerationEngine` must wire the predicate from its existing default `ProviderManager`
- The defensive post-routing backend lookup and explicit failure boundary in `GenerationEngine` must remain
- `Router.select()` returning `None` is an allowed explicit-unavailability result when no executable candidate exists
- The current default Catalog/Registry intersection is empty; GREEN consistency must not be described as operational default video availability
- The test file may contain exactly two contract tests:
  1. a controlled test proving that a higher-scoring unavailable candidate is excluded before scoring and a lower-scoring available candidate is selected, including the all-unavailable `None` result;
  2. a real default-wiring consistency test proving that any returned identity resolves to a registered backend with the same identity, while allowing `None` as explicit unavailability
- The existing availability assertion must not be silently weakened; the test must be renamed/reframed to state the consistency contract accurately
- Expected targeted gate: exactly `4 passed` across the two stage-1E tests and the two provider-identity tests
- Expected full regression gate: exactly `78 passed`, with no failures, skips or xfails
- Do not add `Video AI` to `ProviderCatalog`; it is a deterministic manifest adapter, not a real external video provider
- Do not register or integrate PixVerse
- Do not modify `ProviderCatalog`, `ProviderManager`, `ProviderRegistry`, ModelPolicy, UI, Reactive Orchestrator, documentation or other tests
- Do not add fallback, identity substitution, network access, live APIs, credentials, `.env` access or GUI use
- Existing unrelated dirty-working-tree changes must remain untouched
- After GREEN and verification, stop without commit or push

### DEC-APPROVED-008 — Default Router/Registry consistency RED test

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Base commit: `d84c5b9`
- Related decisions: `DEC-APPROVED-002`, `DEC-APPROVED-005`, `DEC-APPROVED-006`, `DEC-APPROVED-007`
- Authorized stage: 1D — one new RED test for consistency between default routing and the execution registry
- Permitted test file: `tests/test_default_provider_routing_registry_consistency.py`
- Permitted governance worklog: `.ai_exchange/CODEX_WORKLOG.md`
- The test must use the actual default `ProviderRouter` and `ProviderManager`/`ProviderRegistry`
- Fake routers, instance injection, and substitution of `ProviderManager` or `ProviderRegistry` are prohibited
- The test must not hard-code the expected provider identity
- Production code and existing tests must not be changed
- Network, live APIs, credentials, `.env`, and GUI are prohibited
- Stop after the expected RED
- A production fix requires a separate Product Owner decision

### DEC-APPROVED-007 — Stage 1C quality and storage test router injection scope extension

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Related decisions: `DEC-APPROVED-005`, `DEC-APPROVED-006`
- Authorized scope: additional extension of stage 1C
- Permitted additional files only:
  - `tests/test_quality_routing.py`
  - `tests/test_result_storage_flow.py`
- An instance-local router returning the registered `Video AI` provider may be injected only in these three failing tests:
  - `test_generation_engine_resolves_quality_for_video_provider`
  - `test_generation_engine_passes_resolved_quality_to_video_provider`
  - `test_generation_queue_saves_result_through_storage`
- The real `ProviderManager`, `ProviderRegistry`, `GenerationQueue`, quality pipeline, storage, and asset pipeline must remain in use
- Existing assertions must not be changed
- No additional production-code changes are permitted
- Helper files must not be created
- Existing unrelated dirty-working-tree changes must remain untouched
- Full regression gate: exactly `76 passed`, with no failures, skips or xfails
- `76 passed` is not evidence that default automatic routing is ready
- A separate Router → Registry integration test remains a future stage

### DEC-APPROVED-006 — Stage 1C regression-test router injection scope extension

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Related decision: `DEC-APPROVED-005`
- Authorized scope: extension of stage 1C
- Permitted additional files only:
  - `tests/test_full_asset_pipeline.py`
  - `tests/test_generation_pipeline.py`
  - `tests/test_model_generation_flow.py`
- In each permitted test, an instance-local router returning the registered `Video AI` provider may be injected
- The real `ProviderManager`, `ProviderRegistry`, `GenerationQueue`, and asset pipeline must remain in use
- Existing assertions must not be changed
- No additional production-code changes are permitted
- Helper files must not be created
- Targeted GREEN gate: exactly `2 passed`
- Full regression gate: exactly `76 passed`, with no failures, skips or xfails
- Existing unrelated dirty-working-tree changes must remain untouched

### DEC-APPROVED-005 — Minimal provider identity production fix

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Related decisions: `DEC-APPROVED-002`, `DEC-APPROVED-004`
- Related Codex run: `CODEX-RUN-20260903-001`
- Related Copilot review: `MSG-COPILOT-20260903-002`
- Base commit: `b21853c`
- Authorized stage: 1C — minimal provider identity production fix
- Permitted production file: `core/movie_engine/generation_engine.py`
- Permitted test file: `tests/test_provider_execution_identity.py`
- Remove the hidden `PixVerse -> Video AI` alias
- Remove the preliminary implicit `Video AI` fallback
- Resolve the execution backend strictly by routed provider identity
- If the routed backend is unavailable, raise an explicit error before creating or queuing `GenerationTask`
- Preserve the existing identity test as a GREEN invariant
- Add one narrow test in the same test file for explicit failure when the routed backend is unavailable
- Do not register or integrate PixVerse
- Do not modify ProviderManager, ProviderRegistry, Router classes, Provider contracts, ModelPolicy, UI, Reactive Orchestrator, documentation or other tests
- Do not use network, live APIs, real credentials, `.env` or GUI
- Targeted GREEN gate: exactly `2 passed`
- Full regression gate: exactly `76 passed`, with no failures, skips or xfails
- Existing unrelated dirty-working-tree changes must remain untouched
- Codex must introduce changes only to the two permitted stage-1C files
- After GREEN and verification, stop without commit or push

### DEC-APPROVED-004 — GO WITH CONDITIONS / Provider identity RED test

- Status: APPROVED
- Approved by: Sergey, Product Owner
- Date: 2026-09-03
- Stabilization: GO
- New real provider integrations: NO-GO until required gates pass
- Authorized stage: 1B — provider identity RED test only
- The only permitted new file is `tests/test_provider_execution_identity.py`
- The test must compare stable provider identities obtained from the actual routed provider and actual execution boundary
- Expected RED: routed identity `PixVerse` differs from execution identity `Video AI`
- Production code, existing tests and documentation must not be changed
- Network, real API keys, `.env`, GUI and real credentials must not be used
- After obtaining the expected RED, stop without applying a production fix
- Any production fix requires a separate Product Owner decision

### DEC-APPROVED-001 — Authority

- Status: APPROVED
- Sergey is Product Owner and final authority for architecture and strategy.

### DEC-APPROVED-002 — Provider Layer boundary

- Status: APPROVED
- WaveSpeed, Kling and PixVerse are Provider Layer implementations, not Core components.
- AI Director must not silently replace a user-selected provider/model.

### DEC-APPROVED-003 — AI Council roles

- Status: APPROVED
- Jarvis: strategy/product/high-level architecture.
- Copilot: Architect/audit/quality/risk.
- Qwen/Ollama: Local Engineer / Analyst; not Runtime/Core without a separate decision.
- Cursor: implementation environment only.
