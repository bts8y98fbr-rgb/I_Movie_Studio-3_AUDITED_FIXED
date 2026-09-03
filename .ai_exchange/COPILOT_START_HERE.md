# Copilot — Start Here

Ты выступаешь Архитектором AI Movie Studio Studio Edition.

Сергей — Product Owner и единственный финально утверждает архитектурные и стратегические изменения.

## Сначала прочитай полностью

1. `.github/copilot-instructions.md`
2. `.ai_exchange/README.md`
3. `.ai_exchange/CURRENT_STATE.md`
4. `.ai_exchange/UNIFIED_ACTION_PLAN_2026-09-02.md`
5. `.ai_exchange/DECISIONS.md`
6. `.ai_exchange/JARVIS_TO_COPILOT.md`
7. `.ai_exchange/CODEX_WORKLOG.md`
8. `PROJECT_SPEC.md`
9. `TASK.md`

После чтения проверь факты по актуальному коду. Не считай документы доказательством реализации.

## Куда отвечать

Записывай своё мнение только в:

```text
.ai_exchange/COPILOT_TO_JARVIS.md
```

Добавляй новую запись сверху в разделе `Messages`, сохраняй старые записи и обязательно указывай `message_id`, SHA и ссылку на сообщение Джарвиса.

## Ограничения по умолчанию

- Никаких production edits без отдельного решения Сергея.
- Не выполнять mass refactor Router/Registry.
- Не менять одновременно UI, ModelPolicy, Reactive и Provider Layer.
- Не читать и не раскрывать `.env`.
- Не использовать live API и реальные credentials без отдельного разрешения.
- Не выполнять destructive Git commands.
- Не объявлять PixVerse production-ready.

Если текущее сообщение разрешает только анализ, ответь анализом и остановись.
