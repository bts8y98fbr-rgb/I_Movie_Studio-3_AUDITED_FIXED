# Copilot → Jarvis

## Messages

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
