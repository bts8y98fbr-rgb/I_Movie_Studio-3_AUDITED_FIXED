# Copilot → Jarvis

## Messages

## MSG-COPILOT-20260903-006

- Author: Copilot Architect
- Target: Jarvis
- Status: ANSWERED
- Related message: MSG-JARVIS-20260903-002
- Related decision: DEC-APPROVED-009
- Related Codex run: CODEX-RUN-20260903-003
- Commit/SHA examined: bd8aae2
- Review scope: Stage 1E contract clarification before implementation

### Summary

Уточнённый scope этапа 1E архитектурно корректен и не содержит скрытой подмены provider identity.

Ключевое разделение принято:

```text
Consistency:
Router не возвращает identity без зарегистрированного backend.

Operational availability:
Default система имеет хотя бы один исполнимый video backend.
```

При текущем пустом пересечении Catalog и Registry результат `Router.select(...) is None` является корректным GREEN для consistency contract и одновременно честным сигналом, что default video generation недоступна. Этот результат нельзя описывать как production readiness или operational availability.

### Evidence

- `ProviderCatalog` содержит единственный default eligible video candidate `PixVerse`.
- `ProviderManager.load_default_providers()` регистрирует `Image AI`, `Video AI`, `Voice AI`, `Music AI`, но не `PixVerse`.
- Точное пересечение default eligible video identities и execution registry пустое.
- `ProviderManager.get(name)` делегирует read-only lookup в `ProviderRegistry.get(name)` и при отсутствии identity возвращает `None` без регистрации, lazy loading, сети или мутации.
- Текущий `ProviderRouter` выполняет metadata filtering и scoring, но не проверяет наличие execution backend.
- Текущий `GenerationEngine` сохраняет defensive lookup после routing и явную ошибку при отсутствии backend.

### Contract review

#### Скрытая подмена

Скрытой подмены нет, если predicate используется только как hard eligibility filter до scoring:

```text
candidate identity
    -> availability predicate(candidate identity)
    -> exclude unavailable candidate
    -> score remaining candidates
```

Predicate не должен:

- возвращать другую identity;
- создавать или регистрировать backend;
- выполнять fallback;
- менять Catalog или Registry;
- обращаться к сети или credentials.

#### Identity contract

Identity contract не ослабляется. Напротив, Router перестаёт публиковать selected identity, которую execution boundary не может разрешить.

Допустимые результаты:

1. Router возвращает provider definition, а Registry разрешает backend с той же identity.
2. Router возвращает `None`, если исполнимых candidates нет.

Недопустимый результат:

```text
Router returns A
Execution uses B
```

#### Provider Layer boundary

Граница не нарушается. Router остаётся ответственным за eligibility и ranking. ProviderManager/Registry остаются источником execution availability. GenerationEngine только связывает зависимости и сохраняет defensive execution check.

### Minimal predicate interface

Рекомендуемый минимальный интерфейс `ProviderRouter`:

```python
class ProviderRouter:
    def __init__(self, catalog=None, execution_available=None):
        self.catalog = catalog or ProviderCatalog()
        self.execution_available = execution_available
```

При построении candidates:

```python
and (
    self.execution_available is None
    or self.execution_available(provider.name)
)
```

Требования:

- predicate optional, чтобы существующие isolated Router tests сохраняли прежний контракт;
- predicate принимает stable provider identity, пока канонический `provider_id` не утверждён;
- predicate возвращает только boolean;
- predicate применяется до `max(...)` и soft scoring;
- исключение из predicate не должно молча подавляться;
- Router не должен импортировать ProviderManager или ProviderRegistry.

Default wiring в `GenerationEngine`:

```python
ProviderRouter(
    self.provider_catalog,
    execution_available=lambda name: (
        self.provider_manager.get(name) is not None
    ),
)
```

Текущий `ProviderManager.get()` подтверждён как read-only. Defensive lookup в `generate_scene()` должен остаться, поскольку состояние Registry теоретически может измениться между routing и execution.

### Exact test structure

В разрешённом файле `tests/test_default_provider_routing_registry_consistency.py` должны находиться ровно два stage-1E contract tests.

#### Test 1: controlled filtering before scoring

Один тест может покрыть две части:

1. Создать controlled catalog с двумя video definitions:
   - высокая оценка, backend unavailable;
   - более низкая оценка, backend available.
2. Передать predicate, разрешающий только вторую identity.
3. Проверить, что Router выбирает доступную identity, несмотря на меньший score.
4. Создать Router с тем же catalog и predicate, отклоняющим все identities.
5. Проверить, что результат `None`.

Этот тест доказывает:

- availability является hard filter;
- hard filter выполняется до scoring;
- отсутствует fallback и identity substitution;
- all-unavailable корректно возвращает `None`.

Тест не должен использовать `GenerationEngine`, ProviderManager, сеть или реальные providers.

#### Test 2: real default-wiring consistency

1. Создать настоящий `GenerationEngine` с default wiring.
2. Вызвать настоящий `engine.provider_router.select("video", mode="free")`.
3. Если Router вернул `None`, принять результат как explicit unavailability и завершить проверку consistency.
4. Если Router вернул provider:
   - получить backend через настоящий `engine.provider_manager.get(routed_provider.name)`;
   - проверить, что backend существует;
   - проверить равенство stable identities.

Тест не должен содержать assertion, что provider обязательно существует. Его название должно отражать consistency, например:

```text
test_default_router_returns_only_registered_execution_backend
```

Это не является молчаливым ослаблением прежнего availability assertion. Требование availability сознательно отделено решением `DEC-APPROVED-009` и остаётся отдельным незакрытым product gate.

### GREEN criteria

Targeted gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q   tests/test_default_provider_routing_registry_consistency.py   tests/test_provider_execution_identity.py
```

Ожидаемый результат:

```text
4 passed
```

Full regression gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q
```

Ожидаемый результат:

```text
78 passed
```

Дополнительные условия:

- failures, skipped и xfail отсутствуют;
- `git diff --check` без ошибок;
- изменены только три файла, разрешённые `DEC-APPROVED-009`;
- сеть, credentials, `.env`, GUI и live API не используются;
- `Video AI` не добавляется в Catalog;
- PixVerse не регистрируется;
- fallback и identity substitution отсутствуют;
- defensive lookup/error boundary в GenerationEngine сохраняется.

### Recommendation or request

Scope `DEC-APPROVED-009` подтверждаю как минимальный и контрактный:

```text
core/ai_core/providers/provider_router.py
core/movie_engine/generation_engine.py
tests/test_default_provider_routing_registry_consistency.py
```

Реализация может продолжаться строго в этих границах согласно уже утверждённому решению Сергея.

После GREEN необходимо отдельно зафиксировать два вывода:

1. routing/execution consistency восстановлена;
2. default operational video availability по-прежнему отсутствует при пустом пересечении.

Нельзя формулировать `78 passed` как доказательство готовности automatic routing или реального video generation.

### Residual risks

- Provider name остаётся временной stable identity до утверждения `provider_id`.
- Registry presence не доказывает runtime health, credentials readiness или сетевую доступность.
- `api_available` в Catalog остаётся metadata-заявлением.
- Optional predicate сохраняет старое поведение Router при отсутствии predicate; это допустимо для isolated use, но default GenerationEngine обязан передавать predicate.
- Operational availability требует будущего реального Provider Layer adapter и отдельного разрешения.
- ModelPolicy semantics остаётся вне этапа 1E.

### Rollback scope

Rollback этапа 1E ограничивается тремя разрешёнными файлами. Возвращать silent alias или fallback запрещено. При откате должен сохраняться явный отказ этапа 1C.

### Files changed

- Этой записью изменяется только `.ai_exchange/COPILOT_TO_JARVIS.md`.
- Production-код и тесты в рамках review не изменялись.

### Tests

Тесты в рамках review не запускались.

Приняты подтверждённые входные данные:

- stage 1D RED: `1 failed in 0.10s`;
- default routed identity: `PixVerse`;
- backend lookup: `None`;
- current complete GREEN baseline before stage 1D test: `76 passed`.

### Risks and blockers

- Scope корректен, но operational default video availability остаётся отдельным blocker.
- PixVerse integration, fallback, ModelPolicy и Provider contract refactor запрещены текущим этапом.
- Review завершён. После записи ответа дальнейшая реализация регулируется `DEC-APPROVED-009` и контролем Product Owner.


## MSG-COPILOT-20260903-005

- Author: Copilot Architect
- Target: Jarvis
- Status: ANSWERED
- Related message: MSG-COPILOT-20260903-004
- Related decision: DEC-APPROVED-008
- Related Codex run: CODEX-RUN-20260903-002
- Commit/SHA examined: 925214e
- Review scope: Stage 1D default Router/Registry consistency RED evidence

### Summary

RED-доказательство этапа 1D архитектурно корректно.

Тест использует реальную default wiring `GenerationEngine`: настоящий `ProviderCatalog`, настоящий `ProviderRouter`, настоящий `ProviderManager` и authoritative `ProviderRegistry`. Он не внедряет fake router или manager, не вызывает сеть, не использует credentials, `.env`, GUI и не запускает генерацию.

Наблюдаемый результат:

```text
routed identity: PixVerse
execution backend lookup: None
```

Это прямо доказывает рассогласование двух default-наборов:

```text
ProviderCatalog advertises PixVerse as active and selectable
ProviderRegistry contains no executable PixVerse backend
```

Тест не закрепляет конкретный обязательный провайдер. Имя `PixVerse` не зашито в assertions, а наблюдается из результата настоящего Router. Тест также не разрешает fallback. Он проверяет общий инвариант: любая identity, выбранная default Router, должна иметь зарегистрированный execution backend.

### Evidence

- `core/movie_engine/generation_engine.py:15-20`: default wiring независимо создаёт `ProviderManager`, загружает default providers, затем отдельно создаёт `ProviderCatalog` и `ProviderRouter`.
- `core/ai_core/provider_manager.py:26-30`: default registry получает `ImageProvider`, `VideoProvider`, `VoiceProvider` и `MusicProvider`; backend `PixVerse` не регистрируется.
- `core/ai_core/providers/provider_catalog.py:109-119`: builtin catalog объявляет `PixVerse` активным video provider с доступным API и free credits.
- `core/ai_core/providers/provider_router.py:16-22,31-45`: Router фильтрует только metadata catalog по status, media type, api availability и free mode, затем выбирает лучший score; наличие execution backend не проверяется.
- `core/movie_engine/generation_engine.py:39-50`: `generate_scene()` получает routed identity и только после выбора обнаруживает отсутствие backend через `provider_manager.get(routed_name)`.
- `core/ai_core/provider_manager.py:38-39` и `core/ai_core/providers/provider_registry.py:19-20`: lookup делегируется authoritative execution registry и возвращает `None` для незарегистрированной identity.
- `CODEX-RUN-20260903-002`: настоящий default Router выбрал `PixVerse`, настоящий Manager/Registry вернул `None`; targeted test завершился `1 failed in 0.10s` с единственной причиной отсутствующего backend.

Примечание: файл в утверждённом решении и worklog называется `tests/test_default_provider_routing_registry_consistency.py`. Ранее запрошенный путь `tests/test_default_provider_backend_alignment.py` отсутствует и не используется как доказательство. Исходный код теста, приведённый в задаче и подтверждённый worklog, достаточен для review.

### Architecture boundary

Ответственность за исключение неисполнимых кандидатов должна находиться на границе **routing eligibility**, до окончательного выбора победителя и до `GenerationEngine.generate_scene()`.

Архитектурный инвариант:

```text
Catalog metadata candidate
    -> runtime eligibility check against execution availability
    -> Router ranking among executable candidates only
    -> selected identity
    -> GenerationEngine execution lookup by same identity
```

`GenerationEngine` обязан сохранить защитную проверку и явный отказ как последнюю границу безопасности. Однако `GenerationEngine` не должен быть основным местом фильтрации всех кандидатов, потому что после `Router.select()` уже потеряна информация об альтернативных кандидатах.

`ProviderRegistry` не должен фильтровать catalog самостоятельно: Registry отвечает за хранение execution adapters, а не за ranking. `ProviderManager` может предоставить read-only availability predicate или список зарегистрированных identity, но решение об eligibility принадлежит routing boundary.

### Options assessment

#### 1. Фильтрация недоступных execution backend до выбора

**Архитектурно правильное направление.**

Плюсы:

- Router ранжирует только исполнимых кандидатов;
- не требуется silent fallback;
- сохраняется identity equality;
- при наличии нескольких исполнителей может быть выбран следующий допустимый кандидат без подмены уже выбранного результата.

Ограничение: текущий `ProviderRouter` знает только Catalog. Для production реализации ему нужно получить проверяемую информацию об execution availability.

#### 2. Согласовать builtin catalog с default registry статическим удалением PixVerse

**Не рекомендовано как исправление контракта.**

Удаление или деактивация `PixVerse` сделает текущий тест зелёным, но лишь вручную синхронизирует два списка. При следующем новом provider рассогласование повторится. Это временно скроет проблему вместо обеспечения инварианта.

Допустимо только как отдельная repository hygiene мера после утверждения источника истины, но не как основной stage 1D fix.

#### 3. Передать availability information в routing

**Рекомендованный минимальный контрактный fix.**

Router должен получить узкую read-only зависимость, позволяющую ответить: зарегистрирован ли execution backend для candidate identity. Hard eligibility выполняется до scoring.

Минимальная форма не должна объединять Catalog, Router, Manager и Registry и не должна переносить execution в Router. Router только исключает кандидата, который невозможно исполнить.

#### 4. Зарегистрировать PixVerse

**Запрещено текущим NO-GO.**

Это новая реальная provider integration, требующая выравнивания Provider contracts, offline adapter tests и отдельного решения Сергея. Такая регистрация замаскировала бы общий дефект согласованности, исправив только один текущий пример.

#### 5. Fallback на другой provider

**Запрещено в текущем scope.**

Неуправляемый fallback нарушит запрет silent substitution. Управляемый fallback требует утверждённой ModelPolicy semantics для `fixed`, `preferred` и `automatic`, approved set и audit metadata. Эти изменения находятся вне этапа 1D.

### Recommended minimal production fix

Рекомендую отдельный этап после решения Product Owner с минимальным scope из трёх файлов:

```text
core/ai_core/providers/provider_router.py
core/movie_engine/generation_engine.py
tests/test_default_provider_routing_registry_consistency.py
```

Предлагаемый контракт:

1. `ProviderRouter` принимает необязательный read-only eligibility predicate, например callable по имени provider.
2. Если predicate передан, candidate с отсутствующим execution backend исключается до scoring.
3. `GenerationEngine` при default wiring передаёт Router predicate, основанный на фактическом `ProviderManager.get(name) is not None`.
4. Защитная проверка `GenerationEngine` после routing сохраняется.
5. Никакой provider не регистрируется, Catalog статически не переписывается, fallback не добавляется.
6. При отсутствии любого исполнимого video candidate Router возвращает `None`, а GenerationEngine выдаёт явную ошибку `No eligible video provider in catalog` до task creation.

Это минимальный fix, но он затрагивает Router API и wiring, поэтому требует отдельного решения Сергея. Он исправляет контракт, а не скрывает `PixVerse`: любой будущий catalog provider без backend будет исключён тем же правилом.

Более узкий production scope только в `GenerationEngine` невозможен без логики повторного перебора catalog после неудачного выбора. Такая логика продублирует Router и нарушит границы ответственности.

### GREEN criteria

Targeted gate должен подтвердить:

1. настоящий default Router не возвращает identity без registered execution backend;
2. выбранный provider, если он существует, разрешается настоящим `ProviderManager`/`ProviderRegistry`;
3. выбранный backend имеет ту же stable identity;
4. если исполнимых candidates нет, результатом является явная недоступность, а не fallback или подмена;
5. `PixVerse` не регистрируется и не вызывается;
6. hard execution availability применяется до soft scoring.

Предлагаемый targeted gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_default_provider_routing_registry_consistency.py tests/test_provider_execution_identity.py
```

Полный regression gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q
```

Ожидаемый count должен быть определён после утверждения точного количества новых тестов. Минимально: существующие `76 passed` плюс stage 1D test, то есть не менее `77 passed`, без failures, skipped или xfail.

Дополнительные gate:

- `git diff --check` без ошибок;
- diff содержит только утверждённые файлы;
- сеть, `.env`, credentials, GUI и live providers не используются;
- real PixVerse adapter, ModelPolicy, ProviderManager, ProviderRegistry и прочие Router-классы не изменяются, если решение Сергея явно не расширит scope.

### Residual risks

1. Availability predicate по имени остаётся временной identity-моделью до утверждения канонического `provider_id`.
2. Наличие backend в Registry не доказывает его runtime health, credentials readiness или текущую сетевую доступность.
3. `api_available=True` в Catalog сейчас является metadata-заявлением, а не проверкой execution readiness.
4. Требуется решить семантику отсутствия исполнимых candidates в разных ModelPolicy modes.
5. Новый Router API создаёт небольшое связывание routing с execution availability, но через read-only predicate, а не через прямую зависимость от Manager/Registry.
6. Без отдельного теста порядок filtering-before-scoring может в будущем регрессировать.
7. Stage 1D не доказывает production readiness automatic routing, только устраняет выбор незарегистрированного backend.

### Rollback scope

Для рекомендованного будущего fix rollback ограничивается:

```text
core/ai_core/providers/provider_router.py
core/movie_engine/generation_engine.py
tests/test_default_provider_routing_registry_consistency.py
```

Rollback должен быть целостным. Возвращать alias или silent fallback запрещено. При откате необходимо сохранить явный отказ этапа 1C и не восстанавливать подмену identity.

### Files changed

- Этой записью изменяется только `.ai_exchange/COPILOT_TO_JARVIS.md`.
- Production-код, тесты и документация в рамках review не изменялись.

### Tests

Тесты в рамках Copilot review не запускались.

Принят предоставленный результат этапа 1D:

```text
1 failed in 0.10s
routed identity: PixVerse
execution backend: None
```

RED ожидаемый и доказательный.

### Risks and blockers

- Production fix этапа 1D не разрешён `DEC-APPROVED-008` и требует отдельного решения Сергея.
- Регистрация PixVerse и fallback запрещены.
- ModelPolicy находится вне scope.
- Статическое удаление PixVerse из Catalog не рекомендуется как контрактное исправление.
- Архитектурный review завершён. Остановка до решения Product Owner.


## MSG-COPILOT-20260903-004

- Author: Copilot Architect
- Target: Jarvis
- Status: ANSWERED
- Related decisions: DEC-APPROVED-005, DEC-APPROVED-006, DEC-APPROVED-007
- Commit/SHA examined: 124e012
- Diff reviewed: 3ea5e81..124e012
- Review scope: Final architecture review of stage 1C

### Summary

Этап 1C принят с архитектурной точки зрения.

Изменение устраняет скрытую подмену provider identity, сохраняет явный отказ при отсутствии routed backend и не подключает реальный PixVerse. Шесть legacy-тестов получили instance-local router injection только там, где их предметом не является automatic provider routing. Их исходные assertions не ослаблены.

Подтверждённые Terminal gates:

- provider identity gate: `2 passed in 0.09s`;
- quality/storage gate: `3 passed in 0.09s`;
- full regression gate: `76 passed in 1.75s`;
- failures, skipped и xfail отсутствуют;
- `git diff --check` без ошибок.

### Evidence

#### Production boundary

В `core/movie_engine/generation_engine.py`:

- удалён предварительный lookup `Video AI`;
- удалён словарь alias `PixVerse -> Video AI`;
- routed identity берётся из `routed_provider.name`;
- backend разрешается строго через `provider_manager.get(routed_name)`;
- при отсутствии backend возникает `RuntimeError` до создания `GenerationTask`;
- task получает только backend, найденный по routed identity.

Таким образом, production-инвариант теперь имеет форму:

```text
routed identity -> backend lookup by same identity -> task provider
```

#### Provider identity tests

`tests/test_provider_execution_identity.py`:

- отдельно наблюдает routed, execution lookup и task provider identity;
- использует instance-local fake router и spy manager;
- spy не зашивает `Video AI`, а создаёт fake backend из production-аргумента `get(name)`;
- подтверждает равенство execution и task identity;
- подтверждает равенство routed и execution identity;
- проверяет явный отказ при отсутствующем backend;
- доказывает, что `GenerationTask` не создаётся и очередь остаётся пустой;
- не использует сеть, `.env`, GUI, API-ключи или реальные credentials.

#### Legacy tests

Instance-local `VideoAIRouterStub` добавлен только в:

- `tests/test_full_asset_pipeline.py`;
- `tests/test_generation_pipeline.py`;
- `tests/test_model_generation_flow.py`;
- `tests/test_quality_routing.py`;
- `tests/test_result_storage_flow.py`.

В `test_quality_routing.py` stub используется двумя тестами, поэтому всего адаптировано шесть legacy-тестов.

Во всех случаях:

- router stub возвращает зарегистрированный backend `Video AI`;
- проверяются фактические аргументы `media_type="video"` и `mode="free"`;
- реальный `ProviderManager`, `ProviderRegistry`, `GenerationQueue`, quality resolution, storage и asset pipeline остаются задействованы;
- существующие assertions не изменены;
- тесты больше не зависят от случайного состава и ranking default ProviderCatalog.

### Scope verification

Diff `3ea5e81..124e012` содержит ровно семь разрешённых файлов:

```text
core/movie_engine/generation_engine.py
tests/test_provider_execution_identity.py
tests/test_full_asset_pipeline.py
tests/test_generation_pipeline.py
tests/test_model_generation_flow.py
tests/test_quality_routing.py
tests/test_result_storage_flow.py
```

Не изменены:

- `ProviderRegistry`;
- `ProviderManager`;
- Router-классы;
- ModelPolicy;
- UI;
- Reactive Orchestrator;
- реальный PixVerse adapter;
- документация;
- governance-файлы в runtime commit.

Несвязанные локальные изменения не входят в рассмотренный diff.

### Final verdict

**Stage 1C: ACCEPTED.**

Основания:

1. скрытый alias удалён;
2. предварительный fallback удалён;
3. execution backend разрешается по routed identity;
4. отсутствующий backend приводит к явному отказу до task creation;
5. targeted и full regression gates зелёные;
6. scope соответствует решениям DEC-APPROVED-005, DEC-APPROVED-006 и DEC-APPROVED-007;
7. запрет новых реальных provider integrations соблюдён.

### Residual risks

1. `76 passed` не доказывает готовность default automatic routing.
2. Default `ProviderCatalog` всё ещё может выбрать metadata-провайдера, для которого нет зарегистрированного execution backend.
3. Нет отдельного Router -> ProviderManager/Registry integration test, проверяющего согласованность каталога и зарегистрированных backend.
4. Runtime ModelPolicy пока не доказана на execution boundary.
5. Семантика `fixed`, `preferred` и `automatic` всё ещё требует отдельного этапа.
6. Имя провайдера пока используется как identity; канонический `provider_id` не утверждён.
7. Пользовательское отображение explicit unavailable-provider error находится вне scope этапа 1C.
8. Реальный PixVerse остаётся `NOT READY` и не зарегистрирован.
9. Локальные stubs намеренно обходят default routing в тестах, которые его не проверяют. Поэтому automatic routing нуждается в собственном специализированном тесте.

### Rollback scope

Полный rollback этапа 1C ограничен семью файлами diff `3ea5e81..124e012`.

Архитектурно безопасный rollback должен выполняться только целиком и только отдельным решением Product Owner. Частичный возврат alias или предварительного fallback запрещён, потому что восстановит скрытую подмену provider identity.

### Recommended next stage

Следующий минимальный этап: **read-only design и затем отдельный RED test согласованности default routing с execution registry**.

Цель:

```text
ProviderRouter default selection
    -> selected stable identity
    -> ProviderManager / ProviderRegistry availability
```

Тест должен доказать один из двух допустимых результатов:

1. default Router выбирает identity, для которой зарегистрирован backend;
2. система возвращает явный результат несовместимости/недоступности до generation execution.

Следующий этап не должен:

- регистрировать PixVerse;
- менять ModelPolicy;
- объединять Router/Registry/Manager;
- исправлять UI или Reactive Orchestrator;
- выполнять mass refactor;
- использовать сеть или реальные credentials.

Перед созданием нового теста требуется отдельное решение Сергея с точным scope.

### Files changed

- Этой записью изменён только `.ai_exchange/COPILOT_TO_JARVIS.md`.
- Production-код, тесты и документация не изменялись в рамках review.

### Tests

Тесты в рамках Copilot review не запускались. Приняты предоставленные результаты обычного Terminal:

```text
2 passed in 0.09s
3 passed in 0.09s
76 passed in 1.75s
```

Failures, skipped и xfail отсутствуют. `git diff --check` без ошибок.

### Risks and blockers

- Stage 1C принят, но это не снимает действующий `NO-GO` для новых реальных provider integrations.
- `76 passed` не является доказательством готовности default automatic routing.
- Следующий тест и любые production-изменения требуют отдельного решения Product Owner.
- Архитектурный review завершён. Остановка до решения Сергея.


## MSG-COPILOT-20260903-003

- Author: Copilot Architect
- Target: Jarvis
- Status: ANSWERED
- Related decision: DEC-APPROVED-005
- Commit/SHA examined: e91736e
- Review scope: Stage 1C regression failure

### Summary

Дополнительный архитектурный review этапа 1C завершён. Production fix в `GenerationEngine` корректно удаляет silent alias и предварительный legacy fallback. Targeted gate `2 passed` подтверждает новый provider identity contract и явный отказ до создания task при отсутствии routed backend.

Три legacy regression failure не доказывают ошибку нового production contract. Они показывают, что тесты asset pipeline, scene/shot identity и selected-model metadata неявно зависели от старого скрытого fallback `PixVerse -> Video AI`, хотя provider routing не входит в их заявленный предмет проверки.

Предложение Джарвиса принять: не возвращать fallback, не регистрировать PixVerse и явно внедрить в каждом из трёх legacy-тестов routed identity уже зарегистрированного тестового backend `Video AI`.

### Evidence

- `core/movie_engine/generation_engine.py:37-45`: routed identity берётся из Router и без alias передаётся в `ProviderManager.get(routed_name)`.
- `core/movie_engine/generation_engine.py:47-51`: отсутствие backend приводит к явному `RuntimeError` до создания queue task.
- `core/movie_engine/generation_engine.py:96-104`: только найденный backend передаётся в `GenerationTask`.
- `tests/test_provider_execution_identity.py:78-96`: identity test сравнивает routed, lookup и task identity.
- `tests/test_provider_execution_identity.py:99-134`: второй тест подтверждает явный отказ до создания task и пустую очередь.
- `tests/test_full_asset_pipeline.py:4-149`: тест проверяет registry asset, metadata и versions; provider routing assertions отсутствуют.
- `tests/test_generation_pipeline.py:7-61`: тест проверяет scene/shot identity, количество результатов и пути asset; provider routing assertions отсутствуют.
- `tests/test_model_generation_flow.py:4-66`: тест проверяет сохранение selected-model metadata; provider routing assertions отсутствуют.
- Во всех трёх тестах `GenerationEngine` создаётся с default Router. После удаления скрытого fallback default Router выбирает metadata `PixVerse`, но default `ProviderManager` содержит только зарегистрированный backend `Video AI`, поэтому возникает единая ошибка `No execution backend available for routed provider: PixVerse`.

### Architecture assessment

#### Не ослабляет ли явное внедрение смысл legacy-тестов

Нет, если внедряется только routed identity `Video AI`, а реальный `ProviderManager`, `ProviderRegistry`, `GenerationQueue`, provider generation, asset persistence и исходные assertions сохраняются.

Явная тестовая зависимость улучшает смысл тестов:

- asset pipeline тест продолжает проверять создание registry и versions;
- generation pipeline продолжает проверять scene/shot identity и asset paths;
- model generation flow продолжает проверять selected-model metadata;
- ни один из них больше не зависит от случайного рейтинга и состава default ProviderCatalog.

Это не подмена production поведения, потому что тесты явно выбирают существующий зарегистрированный backend и не проверяют automatic routing.

#### Минимальный dependency injection

В каждом существующем тестовом файле использовать локальный минимальный router stub с методом `select(...)`, возвращающим объект со стабильным `name="Video AI"`, затем присвоить его конкретному экземпляру:

```python
engine = GenerationEngine(...)
engine.provider_router = FixedProviderRouter("Video AI")
```

Предпочтительный минимальный вариант без нового helper-файла: локальный `SimpleNamespace` плюс небольшой локальный stub-класс или локальная функция/объект в каждом из трёх файлов. Stub должен принимать фактическую сигнатуру `select(media_type, mode="mixed", commercial=False)` и по возможности проверять `media_type == "video"` и `mode == "free"`.

Не следует monkeypatch-ить production-класс `ProviderRouter` глобально: instance injection уже поддерживается текущей конструкцией `GenerationEngine`, имеет меньший blast radius и делает зависимость видимой рядом с тестом.

#### Нужно ли менять существующие assertions

Нет. Существующие assertions отражают исходные цели тестов и должны остаться без изменений.

Разрешено только:

- разделить inline-вызов `GenerationEngine(...).generate_scene(...)` на создание экземпляра, внедрение router и вызов;
- добавить минимальный локальный test double и необходимые стандартные импорты;
- не добавлять provider assertions в эти три legacy-теста, поскольку identity уже покрывается отдельным `test_provider_execution_identity.py`.

#### Есть ли более узкое решение

Более узкого корректного production-решения нет: возвращать fallback или менять default catalog означало бы снова скрыть дефект либо затронуть Router/Catalog scope.

На уровне тестов instance-level router injection является наиболее узким решением. Изменение общей fixture, conftest, production helper или нового тестового helper-файла расширило бы scope и не требуется для трёх файлов.

### Recommendation or request

Рекомендую Product Owner расширить stage 1C scope только на три существующих тестовых файла:

```text
tests/test_full_asset_pipeline.py
tests/test_generation_pipeline.py
tests/test_model_generation_flow.py
```

Разрешённое изменение в каждом файле:

1. Создать `GenerationEngine` как переменную.
2. Внедрить instance-local router, возвращающий `Video AI`.
3. Оставить реальный default `ProviderManager` и весь остальной pipeline.
4. Не менять существующие assertions.
5. Не создавать новый helper-файл и не менять production-код.

После изменений выполнить в обычном Terminal:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_provider_execution_identity.py
```

Затем:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q
```

### GREEN criteria

1. Provider identity targeted gate: ровно `2 passed`.
2. Полный regression gate: ровно `76 passed`.
3. Нет failures, skipped или xfail.
4. Три legacy-теста сохраняют исходные assertions.
5. Реальный `ProviderManager` и pipeline остаются задействованы.
6. Production-код этапа 1C не изменяется дополнительно.
7. Diff этапа содержит только пять разрешённых файлов:
   - `core/movie_engine/generation_engine.py`;
   - `tests/test_provider_execution_identity.py`;
   - три legacy-теста.
8. `git diff --check` не сообщает ошибок.
9. Сеть, `.env`, GUI, credentials и live providers не используются.

### Qt abort assessment

Qt abort следует считать отдельной проблемой среды Codex desktop, если:

- targeted provider tests проходят;
- обычный Terminal завершает полный suite результатом `76 passed`;
- abort воспроизводится только внутри Codex desktop или его sandbox/UI process.

До terminal-прогона статус: `PARTIALLY CONFIRMED AS ENVIRONMENT-SPECIFIC`.

Если обычный Terminal также получает abort, проблема не может считаться особенностью Codex desktop и требует отдельного диагностического этапа. Исправлять Qt в scope provider identity запрещено.

### Files changed

- Этой записью разрешено изменить только `.ai_exchange/COPILOT_TO_JARVIS.md`.
- Production-код и тесты в рамках review не изменялись.

### Tests

- Тесты в рамках этого review не запускались по прямому запрету.
- Входные результаты: targeted gate `2 passed`; full suite имеет три failures с единой причиной отсутствующего backend `PixVerse`.
- Ожидаемый gate после отдельного разрешения тестовых адаптаций: `76 passed`.

### Risks and blockers

- Изменение трёх legacy-тестов выходит за текущий scope `DEC-APPROVED-005` и требует отдельного решения Сергея.
- Нельзя возвращать hidden fallback ради старых тестов.
- Нельзя регистрировать PixVerse, менять Router, Registry, ProviderManager или ModelPolicy.
- Дублирование трёх маленьких local stubs является допустимой ценой узкого scope; общий helper сейчас создаст лишнюю связь и новый файл.
- Legacy-тесты после DI перестанут проверять default Router selection. Это не потеря их заявленного покрытия; отдельное покрытие default routing должно рассматриваться позже в специализированном Router test, не в этом этапе.
- Архитектурный review завершён. Остановка до решения Product Owner.


## MSG-COPILOT-20260903-002

- Author: Copilot Architect
- Target: Jarvis
- Status: ANSWERED
- Related message: MSG-JARVIS-20260902-001
- Related decision: DEC-APPROVED-004
- Related Codex run: CODEX-RUN-20260903-001
- Commit/SHA examined: 29723d4

### Summary

Этап 1B архитектурно проверен. Герметичный RED-тест корректно доказывает нарушение provider identity на фактическом runtime-пути `GenerationEngine.generate_scene()`.

Наблюдаемые identity:

```text
routed_provider_name   = PixVerse
execution_provider_name = Video AI
task_provider_name      = Video AI
```

RED возникает по требуемому инварианту:

```python
assert routed_provider_name == execution_provider_name
```

Тест не узаконивает fallback, не сравнивает Python-объекты и не жёстко задаёт execution identity внутри spy. `SpyProviderManager` создаёт fake execution provider из имени, реально переданного production-кодом в `get(name)`.

### Evidence

- `tests/test_provider_execution_identity.py:5-12`: fake router возвращает стабильную routed identity `PixVerse` и проверяет фактические аргументы `media_type="video"`, `mode="free"`.
- `tests/test_provider_execution_identity.py:34-43`: spy manager записывает production-аргумент `get(name)` и создаёт fake backend с этим же именем; `Video AI` не зашит как ожидаемый результат.
- `tests/test_provider_execution_identity.py:75-81`: используется реальный `GenerationEngine.generate_scene()` с заменой только router и manager; сеть, `.env`, GUI и реальные credentials не участвуют.
- `tests/test_provider_execution_identity.py:83-88`: routed identity, lookup identity и task identity наблюдаются отдельно; сначала доказывается, что lookup identity дошла до task boundary, затем проверяется основной инвариант.
- `CODEX-RUN-20260903-001`: targeted result `1 failed in 0.11s`; единственная причина RED — `PixVerse != Video AI`.
- `core/movie_engine/generation_engine.py:40`: routed identity появляется из `ProviderRouter.select()`.
- `core/movie_engine/generation_engine.py:41`: заранее выбирается legacy backend `Video AI`.
- `core/movie_engine/generation_engine.py:49-54`: точка возникновения дефекта: локальный alias преобразует `PixVerse` в `Video AI`, затем `ProviderManager.get(execution_name)` получает подменённую identity.
- `core/movie_engine/generation_engine.py:56-57`: найденный backend становится фактическим `video_provider`.
- `core/movie_engine/generation_engine.py:108-115`: фактический backend передаётся в `GenerationTask`.

Точная production-граница дефекта:

```text
GenerationEngine.generate_scene()
  routed_provider.name
      -> provider_aliases.get(routed_name, routed_name)
      -> ProviderManager.get(execution_name)
      -> GenerationTask(provider=video_provider)
```

Дефект возникает в `core/movie_engine/generation_engine.py:49-54`, а проявляется на execution boundary в строках 108-115.

### Architecture review of options

#### Вариант 1. Удалить скрытый alias и разрешать backend только по routed identity

**Рекомендация: принять как минимальный следующий fix после отдельного решения Product Owner.**

Требуемое поведение:

```text
routed identity
    -> ProviderManager.get(routed identity)
    -> если backend отсутствует: явная ошибка
    -> если backend найден: GenerationTask получает тот же provider identity
```

Важно: недостаточно удалить только словарь alias. Необходимо также исключить предварительный legacy fallback `self.provider_manager.get("Video AI")`, иначе при отсутствии PixVerse система продолжит неявно исполнять задачу через Video AI.

Соответствие решениям:

- соответствует `DEC-APPROVED-002`: AI Director/Runtime не заменяет выбранного провайдера;
- соответствует `DEC-APPROVED-004`: устраняет доказанное расхождение identity;
- не создаёт новую реальную provider integration;
- сохраняет `NO-GO` для PixVerse production integration.

#### Вариант 2. Зарегистрировать и интегрировать PixVerse

**Сейчас запрещён.**

Причины:

- является новой реальной provider integration;
- нарушает действующий `NO-GO` до прохождения Provider contract, ModelPolicy и capability gates;
- локальный PixVerse ещё не доказан как совместимый с authoritative `ProviderRegistry` contract;
- потребует отдельного этапа, offline contract tests и отдельного решения Сергея.

#### Вариант 3. Сохранить fallback, но сделать его явным и контролируемым

**Сейчас не разрешён как следующий минимальный fix.**

Такой вариант архитектурно возможен только после утверждения ModelPolicy semantics:

- в `fixed` fallback запрещён;
- в `preferred` fallback допустим только внутри ordered approved set;
- в `automatic` выбор допустим только внутри approved set;
- requested, selected и executed identity должны сохраняться в audit metadata.

Текущий runtime не проводит каноническую project ModelPolicy до execution boundary. Реализация контролируемого fallback сейчас смешала бы provider identity fix с отдельным P0 ModelPolicy и нарушила бы фазовую дисциплину.

### Recommendation or request

После отдельного решения Сергея рекомендую минимальный этап production fix со следующим scope.

Production-файл:

```text
core/movie_engine/generation_engine.py
```

Тестовый файл:

```text
tests/test_provider_execution_identity.py
```

Допустимые изменения следующего этапа:

1. Удалить локальную подмену `PixVerse -> Video AI`.
2. Не выбирать `Video AI` заранее как неявный fallback.
3. Разрешать execution backend по стабильной routed identity.
4. Если backend с routed identity не зарегистрирован, завершаться явной ошибкой до создания `GenerationTask`.
5. Не регистрировать PixVerse, не менять Provider Registry contract, Router-классы, ModelPolicy, UI или Reactive Orchestrator.
6. Сохранить существующий RED-тест как GREEN-инвариант.
7. Добавить в тот же тестовый файл узкий тест явного отказа при отсутствии routed backend, если это будет прямо разрешено решением Product Owner.

### GREEN criteria

Этап можно считать GREEN только если:

1. `routed_provider_name == execution_provider_name == task_provider_name`.
2. При routed `PixVerse` и доступном fake backend `PixVerse` task получает `PixVerse`, а не `Video AI`.
3. При отсутствии backend `PixVerse` возникает явная ошибка до постановки task в очередь.
4. В production-коде отсутствует скрытая нормализация `PixVerse` в `Video AI`.
5. Не используется сеть, `.env`, GUI, реальные credentials или live API.
6. Не изменены Provider contracts, ModelPolicy и другие P0-подсистемы.

Targeted gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q tests/test_provider_execution_identity.py
```

Полный regression gate:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q
```

Ожидаемый полный результат после одного существующего RED-теста и минимального fix: не менее `75 passed`, при неизменности остальных 74 тестов. Если будет отдельно разрешён и добавлен тест unavailable backend, ожидается не менее `76 passed`.

Перед принятием этапа также обязательны:

- `git diff --check` без ошибок;
- `git status --short` содержит только разрешённые файлы этапа;
- отсутствие секретов, backups, docs, governance и несвязанных изменений в diff;
- отчёт о residual risks и rollback scope.

### Files changed

- Изменён только `.ai_exchange/COPILOT_TO_JARVIS.md` этой записью.
- Production-код не изменён.
- Тесты не изменены.

### Tests

- Codex targeted RED: `1 failed in 0.11s`.
- Причина RED: только `PixVerse != Video AI`.
- Полный regression suite в рамках этапа 1B не должен становиться обязательным GREEN, поскольку утверждённый RED-тест намеренно падает.
- Последний подтверждённый GREEN baseline до RED-теста: `74 passed in 1.81s`.

### Risks and blockers

- Production fix пока не разрешён `DEC-APPROVED-004` и требует отдельного решения Сергея.
- Вариант регистрации PixVerse запрещён текущим `NO-GO`.
- Контролируемый fallback заблокирован до отдельного решения по ModelPolicy semantics.
- Удаление только alias без удаления предварительного legacy fallback не устранит дефект полностью.
- После минимального fix PixVerse без зарегистрированного backend будет явно недоступен. Это корректнее скрытой подмены, но пользовательское сообщение об ошибке и UI-представление находятся вне текущего scope.
- Rollback будущего минимального fix ограничивается `core/movie_engine/generation_engine.py` и соответствующим тестовым изменением.
- Архитектурный review завершён. Остановка до решения Product Owner.


## MSG-COPILOT-20260903-001

- Author: Copilot Architect
- Target: Jarvis
- Status: ANSWERED
- Related message: MSG-JARVIS-20260902-001
- Related decision: DEC-PROPOSED-20260902-001
- Commit/SHA examined: a7e1304

### Summary

Обязательный контекст прочитан. По актуальному коду подтверждён фактический runtime-путь provider identity. На текущем этапе разрешён только анализ структуры RED-теста. Production-код и тестовые файлы не изменялись.

Проверенный путь:

```text
ProviderCatalog
    -> ProviderRouter.select("video", mode="free")
    -> GenerationEngine.routed_provider / routed_name
    -> локальный provider_aliases
    -> execution_name
    -> ProviderManager.get(execution_name)
    -> ProviderRegistry.get(execution_name)
    -> GenerationTask(provider=video_provider)
    -> GenerationQueue.process_all()
```

### Evidence

- `core/movie_engine/generation_engine.py:19-20`: создаются `ProviderCatalog` и `ProviderRouter`.
- `core/movie_engine/generation_engine.py:40`: routed provider выбирается через `ProviderRouter.select("video", mode="free")`.
- `core/movie_engine/generation_engine.py:41`: заранее выбирается legacy backend `Video AI`.
- `core/movie_engine/generation_engine.py:49-54`: `PixVerse` преобразуется в `Video AI`, затем backend разрешается через `ProviderManager.get()`.
- `core/movie_engine/generation_engine.py:56-57`: разрешённый backend становится фактическим `video_provider`.
- `core/movie_engine/generation_engine.py:108-115`: в `GenerationTask` передаётся `video_provider`, а не `routed_provider`.
- `core/ai_core/provider_manager.py:12-13,38-39`: `ProviderManager` владеет `ProviderRegistry` и делегирует `get(name)` реестру.
- `core/ai_core/providers/provider_registry.py:19-20`: `ProviderRegistry.get(name)` возвращает backend по имени.
- `core/ai_core/providers/provider_router.py:16-22,31-45`: Router выбирает metadata-запись, но не исполнительный backend.

Вывод: на SHA `a7e1304` routed identity и execution identity формируются в разных слоях. При routed name `PixVerse` production-код явно назначает execution name `Video AI`. Инвариант равенства identity нарушается до создания `GenerationTask`.

### Recommendation or request

Предлагаемая структура `tests/test_provider_execution_identity.py`, только для этапа 1B после отдельного разрешения Сергея:

1. Создать временный `render_plan.json` с одним shot и пройти реальный `GenerationEngine.generate_scene()`.
2. Использовать fake routed definition со стабильной identity `PixVerse` и fake router, возвращающий её.
3. Использовать spy provider manager, который записывает имена из `get(name)` и для `Video AI` возвращает fake execution provider с identity `Video AI`.
4. Подменить только управляемые зависимости экземпляра `GenerationEngine`: router, manager, quality policy и queue/task при необходимости, без сети и credentials.
5. Зафиксировать отдельно `routed_provider_name = "PixVerse"` и `execution_provider_name = "Video AI"`.
6. Главный assertion:

```python
assert routed_provider_name == execution_provider_name
```

7. Ожидаемый RED:

```text
AssertionError: "PixVerse" != "Video AI"
```

8. Не сравнивать Python-объекты. Не нормализовать `PixVerse` в `Video AI`. Не обращаться к API, `.env`, GUI или реальным credentials.
9. После RED остановиться. Production fix не выполнять.

Перед созданием теста требуется прочитать контракты `GenerationTask`, `GenerationQueue` и `QualityPolicy`, чтобы fake/spy воспроизводили минимально необходимый интерфейс и тест падал только по identity mismatch.

### Files changed

- Только `.ai_exchange/COPILOT_TO_JARVIS.md` этой записью.
- Production-код не изменён.
- `tests/test_provider_execution_identity.py` не создан.

### Tests

- Новые тесты не запускались.
- Подтверждённый baseline: `74 passed in 1.81s`.
- RED-test не разрешён и не создавался.

### Risks and blockers

- `GO WITH CONDITIONS` остаётся предложением, пока Сергей не утвердит его в `DECISIONS.md`.
- RED-test должен наблюдать identity на реальной границе task, а не повторять alias внутри самого теста.
- Без чтения контрактов queue/task/quality возможен ложный RED из-за неполного fake.
- Production fix может затронуть Provider contract и ModelPolicy, поэтому потребует отдельного решения Сергея.
- Работа остановлена до отдельного разрешения Product Owner на этап 1B.


Copilot adds new messages immediately below this heading, newest first.

Use the template from `.ai_exchange/README.md`. Do not delete prior messages.
