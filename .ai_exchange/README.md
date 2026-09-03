# AI Council GitHub Exchange

Этот каталог — общий версионируемый канал обмена между Сергеем, Джарвисом, Copilot и локальным Codex.

GitHub не является чатом реального времени. Новая запись становится доступна другим участникам после commit/push и обновления их локальной или облачной копии репозитория.

## Обязательный порядок чтения

1. `COPILOT_START_HERE.md`
2. `CURRENT_STATE.md`
3. `UNIFIED_ACTION_PLAN_2026-09-02.md`
4. `DECISIONS.md`
5. Свой входящий канал:
   - Copilot читает `JARVIS_TO_COPILOT.md`;
   - Джарвис читает `COPILOT_TO_JARVIS.md`;
   - оба читают `CODEX_WORKLOG.md`.

## Владение файлами

| Файл | Кто пишет | Кто читает |
|---|---|---|
| `JARVIS_TO_COPILOT.md` | Джарвис | Copilot, Сергей |
| `COPILOT_TO_JARVIS.md` | Copilot | Джарвис, Сергей |
| `CODEX_WORKLOG.md` | Сергей добавляет выводы локального Codex | Джарвис, Copilot |
| `DECISIONS.md` | Сергей либо Джарвис после прямого утверждения Сергея | Все |
| `CURRENT_STATE.md` | Джарвис после сверки доказательств | Все |
| `UNIFIED_ACTION_PLAN_2026-09-02.md` | Джарвис; изменения требуют решения Сергея | Все |

Участник не переписывает чужой исходящий канал. Ответ оформляется в собственном исходящем файле со ссылкой на `message_id`.

## Формат сообщения

```markdown
## MSG-AUTHOR-YYYYMMDD-NNN

- Author:
- Target:
- Status: NEW | ACK | ANSWERED | CLOSED
- Related message:
- Related decision:
- Commit/SHA examined:

### Summary

### Evidence

### Recommendation or request

### Files changed

### Tests

### Risks and blockers
```

## Правила

1. Каждая запись получает уникальный `message_id`.
2. Новые записи добавляются сверху под заголовком `Messages`; историю не удалять.
3. ACK создаётся в собственном исходящем канале и ссылается на исходный ID.
4. Решение считается утверждённым только после записи Сергея в `DECISIONS.md`.
5. Мнение Copilot обязательно к рассмотрению, но не заменяет решение Product Owner.
6. Документация не считается доказательством без runtime-кода и тестов.
7. Не размещать `.env`, ключи, токены, OAuth-коды, пароли и credential-bearing URLs.
8. Полные большие логи Codex хранить отдельным файлом в `codex_runs/`, а в `CODEX_WORKLOG.md` добавлять индекс и выводы.
9. Code, tests, docs, governance и cleanup не смешивать в одном commit.
10. Governance exchange не импортируется Runtime-кодом.

## Рекомендуемые commit prefixes

```text
council(jarvis): ...
council(copilot): ...
council(codex): ...
decision: ...
```
