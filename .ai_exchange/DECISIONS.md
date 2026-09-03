# AI Council Decision Log

Only decisions explicitly approved by Sergey are recorded as `APPROVED`.

## Proposed decisions awaiting Sergey

## Approved standing decisions

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
