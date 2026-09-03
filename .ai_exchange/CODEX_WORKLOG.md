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
