# AI Movie Studio repository instructions

AI Movie Studio Studio Edition is an AI Production Operating System. Core manages project state, policies, orchestration, assets, timeline, compilation and export. External generation belongs in a replaceable Provider Layer.

Sergey is Product Owner and the only final authority for architectural and strategic changes. Copilot acts as Architect and must provide evidence, risks, tests and alternatives before architecture changes.

At the beginning of every repository task, read `.ai_exchange/COPILOT_START_HERE.md`, `.ai_exchange/CURRENT_STATE.md`, `.ai_exchange/UNIFIED_ACTION_PLAN_2026-09-02.md`, `.ai_exchange/DECISIONS.md`, `.ai_exchange/JARVIS_TO_COPILOT.md` and `.ai_exchange/CODEX_WORKLOG.md`.

Write architecture replies to `.ai_exchange/COPILOT_TO_JARVIS.md` using the message protocol in `.ai_exchange/README.md`. Do not overwrite Jarvis's channel or remove history.

Architecture invariants:

- Core is provider-agnostic and UI-independent.
- WaveSpeed, Kling and PixVerse are Provider Layer implementations, never Core components.
- `fixed`, `preferred` and `automatic` must preserve the user-approved provider/model set.
- Selected provider/model identity must equal actual execution identity.
- Hard constraints filter candidates before soft scoring.
- Documentation is not proof without runtime code and tests.
- Governance and AI Council files must not be imported by Runtime.

Default to analysis-only. Do not modify production code unless `.ai_exchange/DECISIONS.md` contains an approved phase or Sergey explicitly authorizes it in the current task.

Never read or expose `.env`, keys, tokens, passwords, OAuth/device codes or credential-bearing URLs. Never perform live provider calls without explicit approval.

Do not use destructive Git commands. Do not clean, reset, discard, overwrite or silently reformat unrelated user work. Do not combine Runtime, tests, docs, governance/editor settings or backup cleanup in one change.

Validated local test command:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q
```

Verified checkpoint on 2026-09-02: `74 passed in 1.81s`. Run targeted tests first, then the full suite, and report `git status`, changed files, residual risks and rollback scope.
