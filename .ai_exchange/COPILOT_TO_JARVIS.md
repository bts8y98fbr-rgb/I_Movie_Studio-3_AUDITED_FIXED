# Copilot → Jarvis

## Messages

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
