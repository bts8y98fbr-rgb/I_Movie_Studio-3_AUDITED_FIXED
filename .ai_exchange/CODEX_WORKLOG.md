# Local Codex Worklog

Сергей добавляет сюда результаты локального Codex. Джарвис и Copilot читают этот файл перед новыми архитектурными выводами.

## How to append

Для короткого вывода добавьте новую запись сверху под `Entries`.

Для большого полного отчёта:

1. создайте `.ai_exchange/codex_runs/YYYY-MM-DD_RUN-NNN.md`;
2. вставьте полный вывод без секретов;
3. добавьте здесь краткое резюме и ссылку;
4. укажите SHA, режим Codex, команду теста и результат.

Никогда не добавляйте `.env`, API keys, OAuth/device codes или credential URLs.

## Entries

## CODEX-RUN-20260903-005

- Mode: ChatGPT Work isolated repository worktree, stage 2A fixed ModelPolicy execution-boundary RED test
- Repository base: `49e6baf`
- Related decision: `DEC-APPROVED-010`
- Test file: only new `tests/test_runtime_model_policy_boundary.py`
- Test command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_runtime_model_policy_boundary.py`
- Test result: `1 failed in 0.03s`
- RED reason: `GenerationQueue.process_next()` ignored the canonical fixed `task.model_policy` and called `provider.generate()` with a different selected model identity

### Observed identities and boundary

- Fixed requested provider: `Requested Provider`
- Fixed requested model: `requested-model`
- Executed provider: `Executed Provider`
- Selected model passed to execution: `executed-model`
- Observed provider calls: one; the required count is zero
- Proven boundary: `GenerationTask(model_policy) -> GenerationQueue.process_next() -> provider.generate()`

### Scope and controls

- The test uses the actual `GenerationTask`, actual `GenerationQueue`, and canonical `core.ai_core.model_policy.ModelPolicy` with `SelectionMode.FIXED`.
- The spy provider only records calls and performs no network or external I/O.
- Production code and existing tests were not changed.
- UI ModelPolicy, project persistence, preferred/automatic semantics, fallback, PixVerse, Provider Registry, ModelPolicy production implementation, and Reactive Orchestrator were not changed.
- Plugin autoload was disabled only because the isolated Linux environment lacks the system Qt library; the targeted test does not use Qt.
- The full regression suite was not run because the approved stage requires stopping after the expected RED.
- A production fix requires a separate Product Owner decision.

## CODEX-RUN-20260903-004

- Mode: ordinary macOS Terminal, stage 1E operational GREEN verification
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Implementation commit: `bb83d02`
- Related decision: `DEC-APPROVED-009`
- Related Copilot review: `MSG-COPILOT-20260903-007`
- Results source: exact Terminal output provided by Sergey after applying the stage 1E patch; the guarded commit/push ran only after both gates and diff-check succeeded
- Targeted command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_default_provider_routing_registry_consistency.py tests/test_provider_execution_identity.py`
- Targeted result: `4 passed in 0.12s`
- Full regression command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q`
- Full regression result: `78 passed in 1.71s`
- Failures: `0`
- Skipped: `0`
- Xfail: `0`
- `git diff --check`: no errors

### Operational conclusion

- Routing/execution consistency is restored: default routing cannot return an identity without a registered execution backend when the availability predicate is wired.
- Default operational video availability remains absent because the default eligible video Catalog identities and registered execution backend identities still have an empty intersection.
- `78 passed` does not prove that default automatic routing is ready for production.
- PixVerse remains `NOT READY` and is not registered as an execution backend.
- New provider integrations and fallback remain prohibited.
- Any next code stage requires a separate Product Owner decision.

### Scope and controls

- This entry records already completed Terminal verification only.
- Production code and tests were not changed while recording this entry.
- No fallback, provider registration, identity substitution, ModelPolicy change, network access, live API, credentials, `.env`, or GUI use was introduced.

## CODEX-RUN-20260903-003

- Mode: Codex desktop, read-only analysis before a Product Owner decision on the stage 1D production fix
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Related decision: `DEC-APPROVED-008`
- Analysis method: source inspection and local Python introspection only

### Catalog and Registry identities

- Default eligible video Catalog identities: `PixVerse`
  - status: `active`
  - media types: `["video"]`
  - API available: `true`
  - free API: `false`
  - free credits: `true`
  - free-mode eligible: `true`
  - quality score: `8.5`
  - speed score: `8.0`
  - ranking total: `16.5`
- Default registered execution backend identities: `Image AI`, `Video AI`, `Voice AI`, `Music AI`
- Exact intersection of eligible default video Catalog identities and registered execution backend identities: empty set

### Availability predicate simulation

Simulated predicate:

```python
backend_available(name) = provider_manager.get(name) is not None
```

- `backend_available("PixVerse")` evaluated to `False`.
- Filtered candidates: `PixVerse`.
- Remaining candidates: none.
- Simulated Router result after filtering before scoring: `None`.

### ProviderManager.get(name) side effects

- Actual call path: `ProviderManager.get(name) → ProviderRegistry.get(name) → self.providers.get(name)`.
- Missing identities return `None`.
- Registry keys were unchanged before and after lookup.
- Registered provider object identities were unchanged before and after lookup.
- No registration, lazy loading, network access, credential access, or other mutation occurs in the current implementation.
- Therefore `provider_manager.get(name) is not None` is safe as a read-only availability predicate under the current contract; a separate `has`/`contains` contract is not required for the minimal fix, though it could make a future side-effect-free contract more explicit.

### Compatibility with the current RED test

- An availability-predicate fix would filter out `PixVerse` and make the default Router return `None`.
- `tests/test_default_provider_routing_registry_consistency.py` would not become GREEN unchanged.
- It would continue to fail at `assert routed_provider is not None` with `default Router returned no eligible video provider`.
- The current test combines two distinct requirements:
  1. consistency — Router must not return an identity without an execution backend;
  2. availability — the default system must have at least one executable video backend.
- Returning `None` is supported by the current Router contract and is a valid explicit-unavailability result, but it also proves that default generation remains unavailable.

### Recommended future scope

Minimal production scope:

- `core/ai_core/providers/provider_router.py`: add an optional execution-availability predicate and apply it while building candidates, before scoring.
- `core/movie_engine/generation_engine.py`: wire the predicate from the existing default `ProviderManager` without changing identity or adding fallback.

Minimum test scope requires two distinct tests:

1. A controlled filtering-before-scoring test where a higher-scoring unavailable candidate is excluded and a lower-scoring available candidate is selected; an all-unavailable case must produce `None`.
2. The current default-wiring test retained as a separate operational availability gate, so default generation unavailability is not hidden.

The predicate-only fix can satisfy consistency but cannot make the current availability gate GREEN because the Catalog/Registry intersection is empty. If Product Owner accepts `Router=None` as the completed-stage outcome, the current test must be explicitly redefined as consistency-only and GREEN must not be presented as proof that default generation is operational.

### Scope and controls

- No production code or tests were changed during this analysis.
- No network, live API, credentials, `.env`, or GUI were used.
- No provider registration, silent fallback, identity substitution, ModelPolicy change, or static removal of PixVerse was proposed or performed.

## CODEX-RUN-20260903-002

- Mode: Codex desktop, stage 1D default Router/Registry consistency RED test
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Base commit: `d84c5b9`
- Related decision: `DEC-APPROVED-008`
- Test file: only new untracked `tests/test_default_provider_routing_registry_consistency.py`
- Test command: `PATH="$PWD/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_default_provider_routing_registry_consistency.py`
- Test result: `1 failed in 0.10s`
- Routed identity: `PixVerse`, observed from the actual default `ProviderRouter`
- Execution backend lookup: `None`, returned by the actual default `ProviderManager`/`ProviderRegistry` for the routed identity
- RED reason: `default routed provider 'PixVerse' has no registered execution backend`

### Scope and controls

- The test uses the default `GenerationEngine` wiring without fake routers, instance injection, manager/registry substitution, monkeypatching, render plans, or `generate_scene()`.
- Network, live APIs, credentials, `.env`, and GUI were not used.
- Production code and existing tests were not changed.
- Stage 1D is stopped after the expected RED and awaits Copilot review and a separate Product Owner decision before any production fix.

## CODEX-RUN-20260903-001

- Mode: Codex desktop, stage 1B governance record
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Base commit: `7d5a31f`
- Related decision: `DEC-APPROVED-004`
- Stage: 1B — provider identity hermetic RED test, completed and stopped
- File created: only untracked `tests/test_provider_execution_identity.py`
- Test command: `pytest -q tests/test_provider_execution_identity.py`
- Test result: `1 failed in 0.11s`
- RED reason: only `PixVerse != Video AI`

### Observed identities

- Routed: `PixVerse`
- Execution: `Video AI`
- Task provider: `Video AI`

### Proven runtime path

`GenerationEngine.generate_scene → FakeProviderRouter → production alias → SpyProviderManager.get(name) → FakeExecutionProvider(name) → GenerationTask → GenerationQueue`

The final hermetic version does not call the real `ProviderManager.get()` or `ProviderRegistry.get()`. `SpyProviderManager.get(name)` records the actual production argument and constructs the fake execution provider with that same `name`; it does not hard-code the execution identity.

### Full test source

```python
import json
from types import SimpleNamespace


class FakeProviderRouter:
    def __init__(self):
        self.routed_provider = SimpleNamespace(name="PixVerse")

    def select(self, media_type, mode="mixed", commercial=False):
        assert media_type == "video"
        assert mode == "free"
        return self.routed_provider


class FakeExecutionProvider:
    def __init__(self, name):
        self.name = name

    def capabilities(self):
        return {
            "resolutions": ["3840x2160"],
            "fps": [60],
            "hdr": [True],
            "color_depth": [10],
        }

    def generate(self, prompt, **kwargs):
        return {
            "status": "success",
            "provider": self.name,
        }


class SpyProviderManager:
    def __init__(self):
        self.get_calls = []
        self.providers = {}

    def get(self, name):
        self.get_calls.append(name)
        if name not in self.providers:
            self.providers[name] = FakeExecutionProvider(name)
        return self.providers[name]


def test_routed_provider_identity_reaches_execution_boundary(tmp_path):
    from core.movie_engine.generation_engine import GenerationEngine

    render_dir = tmp_path / "render" / "scene_001"
    render_dir.mkdir(parents=True)

    render_plan = {
        "scene_id": 1,
        "render_settings": {
            "resolution": "3840x2160",
            "fps": 60,
            "hdr": True,
            "color_depth": 10,
        },
        "shots": [
            {
                "shot_id": 1,
                "director_prompt": "Provider identity boundary test",
                "timeline": {"duration": 1},
                "camera": {},
            }
        ],
    }

    (render_dir / "render_plan.json").write_text(
        json.dumps(render_plan),
        encoding="utf-8",
    )

    engine = GenerationEngine(project_path=tmp_path, quality="4k")
    fake_router = FakeProviderRouter()
    spy_manager = SpyProviderManager()
    engine.provider_router = fake_router
    engine.provider_manager = spy_manager

    engine.generate_scene(1)

    routed_provider_name = fake_router.routed_provider.name
    execution_provider_name = spy_manager.get_calls[-1]
    task_provider_name = engine.queue.tasks[0].provider.name

    assert execution_provider_name == task_provider_name
    assert routed_provider_name == execution_provider_name
```

### Scope and controls

- Network, APIs, credentials, `.env`, and GUI were not used.
- Production code, existing tests, and documentation were not changed.
- The RED test has not been added to Git and must not be published to `main` before a separate decision on the production fix.
- Stage 1B is stopped and awaits Copilot architectural review and a Product Owner decision.

## CODEX-RUN-20260902-001

- Mode: Codex CLI `0.152.1`, `gpt-5.6-sol`, sandbox `read-only`
- Repository: local `I_Movie_Studio-3_AUDITED_FIXED`
- Audited SHA: `820ed1aac626e80ccf1049a2e51d8a199020035a`
- File coverage: 268 found, 266 UTF-8 files read, `.env` and SQLite contents excluded
- Static verdict: `NOT READY` for PixVerse production runtime
- Test run after audit: `74 passed in 1.81s`
- Test command: `PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q`
- Post-test status: unchanged

### Key findings

- PixVerse is in Provider Layer but not in the active execution path.
- PixVerse is aliased to Video AI.
- Provider base contracts conflict.
- ModelPolicy does not control runtime.
- ProviderPool and CapabilityMatcher allow routing errors.
- Reactive regeneration duplicates scene state.
- Initial ordinary timeline overlap was not confirmed.
- Documentation is ahead of runtime.
