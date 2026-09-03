# AI Council Decision Log

Only decisions explicitly approved by Sergey are recorded as `APPROVED`.

## Proposed decisions awaiting Sergey

## Approved standing decisions

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
