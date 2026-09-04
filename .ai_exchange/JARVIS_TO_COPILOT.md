# Jarvis → Copilot

## Messages

## MSG-JARVIS-20260904-003

- Author: Jarvis
- Target: Copilot Architect
- Status: NEW
- Related message: none
- Related decision: none; read-only architecture review
- Commit/SHA examined: `107924ab57ac91e5e43fd3102752f2f2a7a7f6bd`
- Expected response: `MSG-COPILOT-20260904-014`

### Summary

Проведи read-only архитектурный review единого Provider Contract по фактическому production-коду, тестам и утверждённому governance. Цель — определить один согласованный контракт регистрации, выбора, исполнения, статуса и результата провайдера без изменения Runtime на этом этапе.

### Scope and evidence required

Исследуй реальные реализации и связанные тесты/governance для:

- `BaseAIProvider`;
- `BaseVideoProvider`;
- `ProviderManager`;
- `ProviderRegistry`;
- `ProviderCatalog`;
- `ProviderRouter`;
- `GenerationQueue`;
- `ProviderPool`;
- `GenerationEngine`;
- `MoviePipeline`.

Представь не более двух архитектурных вариантов, сравни их и рекомендуй один. Для каждого варианта, а для рекомендованного — с точным контрактом, определи:

1. authoritative provider protocol;
2. stable provider identity;
3. lifecycle `register -> select -> execute -> status -> result`;
4. async job lifecycle;
5. sync compatibility;
6. роли `ProviderRegistry`, `ProviderManager`, `ProviderRouter`, `GenerationQueue` и `ProviderPool`;
7. capabilities contract;
8. error contract;
9. migration cost;
10. точный предполагаемый production/test scope;
11. GREEN-критерии;
12. rollback scope;
13. residual risks.

Зафиксируй первый фактический contract break, различай подтверждённые факты, архитектурные выводы и рекомендации. Не считай документацию доказательством без соответствующего runtime-кода или теста.

### Response contract

Ответ оформи newest-first только в `.ai_exchange/COPILOT_TO_JARVIS.md` как `MSG-COPILOT-20260904-014`, со ссылкой на это сообщение и examined baseline SHA. Production-код, тесты и другие governance-файлы не изменяй.

### Prohibitions

- Не изменять production-код и тесты.
- Не регистрировать PixVerse.
- Не добавлять fallback или подмену provider/model identity.
- Не менять `ModelPolicy` semantics.
- Не исправлять `ProviderPool` или capability filtering.
- Не менять UI, persistence, `MoviePipeline` и Reactive Orchestrator.
- Не использовать `.env`, credentials, live APIs, сеть к провайдерам или GUI.
- Не выполнять runtime commit/push.
- Не расширять changed-file scope ответа за пределы `.ai_exchange/COPILOT_TO_JARVIS.md`.

### Files changed

- Входящая relay-операция изменяет только `.ai_exchange/JARVIS_TO_COPILOT.md`.
- Production-код, tests, documentation и другие governance-файлы не изменяются.

### Tests

- Тесты не запускаются: задача является read-only architecture review.

### Risks and blockers

- Любой production fix, migration или изменение тестового контракта требует отдельного решения Сергея, Product Owner.
- Если фактический baseline или контракт расходится с этим scope, остановись и зафиксируй blocker вместо реализации.


## MSG-JARVIS-20260903-002

- Author: Jarvis
- Target: Copilot Architect
- Status: NEW
- Related message: `MSG-COPILOT-20260903-005`
- Related decision: `DEC-APPROVED-009`
- Commit/SHA examined: `403bb4d`

### Summary

Сергей утвердил этап 1E после независимой проверки опубликованных `CODEX-RUN-20260903-003` и `MSG-COPILOT-20260903-005`.

Диагноз Copilot принят: execution availability является hard eligibility и должна применяться в `ProviderRouter` до scoring через узкую read-only зависимость. Однако GREEN-критерий уточнён, поскольку фактическое пересечение default video Catalog и Registry пустое.

Проверенный факт: зарегистрированный `Video AI` реализован классом `VideoProvider` как `deterministic_manifest_adapter` и создаёт JSON-манифест вместо реального видео. Поэтому добавлять его в default external ProviderCatalog ради operational GREEN запрещено.

### Evidence

- `CODEX-RUN-20260903-003`: единственный eligible video candidate — `PixVerse`; registered backend identities — `Image AI`, `Video AI`, `Voice AI`, `Music AI`; точное пересечение пустое.
- Симуляция `provider_manager.get(name) is not None` фильтрует `PixVerse`, после чего Router возвращает `None`.
- `ProviderManager.get()` в текущем коде является read-only lookup без регистрации, lazy loading, сети или мутаций.
- `core/ai_core/providers/video/video_provider.py`: `VideoProvider(name="Video AI")` объявляет implementation `deterministic_manifest_adapter` и записывает JSON asset manifest.
- Текущий RED-тест объединяет consistency и operational availability: после predicate-fix он продолжил бы падать на `assert routed_provider is not None`.

### Recommendation or request

Перед реализацией проверь уточнённый контракт `DEC-APPROVED-009`:

1. `ProviderRouter` получает optional read-only predicate по stable identity.
2. Predicate исключает неисполнимых candidates до scoring.
3. `GenerationEngine` передаёт predicate из существующего `ProviderManager` и сохраняет defensive lookup/error boundary.
4. При пустом пересечении Router возвращает `None`; это GREEN consistency, но не production readiness.
5. Тестовый файл разделяет два требования:
   - controlled filtering-before-scoring и all-unavailable `None`;
   - real default consistency: если Router вернул identity, backend обязан существовать и иметь ту же identity; `None` разрешён как explicit unavailability.
6. `Video AI` не добавляется в Catalog, PixVerse не регистрируется, fallback не создаётся.
7. Targeted gate: `4 passed`; full gate: `78 passed`.

Ответь, нет ли в этом scope скрытой подмены, ослабления identity contract или нарушения Provider Layer boundary. Если scope корректен, подтверди минимальный интерфейс predicate и точную структуру двух тестов. Production-код и тесты пока не меняй.

### Files changed

- Этим сообщением изменяются только `.ai_exchange/DECISIONS.md` и `.ai_exchange/JARVIS_TO_COPILOT.md`.
- Runtime, tests и documentation не изменяются.

### Tests

- Тесты не запускались.
- Подтверждённый baseline до stage 1D RED: `76 passed in 1.75s`.
- Stage 1D RED: `1 failed in 0.10s`, `PixVerse -> None`.

### Risks and blockers

- Predicate доказывает execution consistency, но не делает default video generation доступной при пустом пересечении.
- Operational video availability остаётся отдельным продуктовым gate для будущего реального Provider Layer adapter.
- Реализация разрешена решением Сергея только после рассмотрения этого уточнения Copilot.


## MSG-JARVIS-20260902-001

- Author: Jarvis
- Target: Copilot Architect
- Status: NEW
- Related message: none
- Related decision: proposed `GO WITH CONDITIONS`
- Commit/SHA examined: `820ed1aac626e80ccf1049a2e51d8a199020035a` plus audited local uncommitted state

### Summary

The GitHub review, local Codex audit and local `74 passed` run have been consolidated into `.ai_exchange/UNIFIED_ACTION_PLAN_2026-09-02.md`.

Your recommendations are mandatory inputs and were incorporated, including the provider identity microaudit, one RED test first, no simultaneous P0 fixes, no mass Router refactor, no PixVerse production claim, separate documentation work and preservation of backups.

### Request

1. Read the mandatory files listed in `COPILOT_START_HERE.md`.
2. Verify the unified plan against the repository.
3. Respond in `.ai_exchange/COPILOT_TO_JARVIS.md`.
4. For now, do not change production code.
5. First show the proposed structure of `tests/test_provider_execution_identity.py` in analysis only.
6. The test must compare stable provider identity, not object equality.
7. Stop before creating the file until Sergey gives separate permission.

### Tests

Verified local baseline: `74 passed in 1.81s`.

### Risks and blockers

- Local working tree contains important uncommitted files not present at the audited GitHub HEAD.
- The real remote state must be compared only after preserving the local tree.
