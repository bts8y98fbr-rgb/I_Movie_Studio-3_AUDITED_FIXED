# AI Movie Studio — Пункт 5: Реальные AI-провайдеры

## Статус

- 🔄 5. Реальные AI-провайдеры
  - ✅ LLM: Gemini
  - ✅ LLM: Groq
  - ✅ LLM: OpenRouter
  - ✅ Image/Audio: Stability AI
  - ✅ Voice: ElevenLabs
  - ✅ Video: PixVerse API обнаружен
  - 🔄 Video: продолжается проверка остальных API
  - ⬜ Единый Provider Registry
  - ⬜ Автоматическое обновление каталога
  - ⬜ Режимы FREE / MY KEYS / MIXED
  - ⬜ Quota / Health monitoring
  - ⬜ Automatic fallback
  - ⬜ Реальные API adapters
  - ⬜ UI управления провайдерами

## Архитектурный принцип

AI Movie Studio работает как дирижёр/оркестратор.

Локальная машина:
- принимает задачу;
- анализирует требования;
- выбирает модель и провайдера;
- проверяет доступность, квоты, качество и скорость;
- отправляет задачу во внешний AI-сервис;
- отслеживает job;
- принимает результат;
- регистрирует asset и версию.

Фактическая тяжёлая AI-генерация выполняется на ресурсах внешних нейросетевых сервисов.

## Схема

Movie task
    ↓
AI Director
    ↓
Capability Router
    ↓
FREE + USER KEYS
    ↓
Health + Quota + Quality + Speed
    ↓
BEST PROVIDER
    ↓
Remote API
    ↓
Generation Job
    ↓
Asset Registry

## Режимы пользователя

### FREE
Используются доступные бесплатные сервисы.

### MY KEYS
Используются только API-ключи пользователя.

### MIXED
Оркестратор автоматически выбирает оптимальный источник:
- бесплатный сервис;
- пользовательский ключ;
- fallback на другой доступный provider.

## Provider Catalog

Для каждого провайдера храним:

- identity
- capabilities
- models
- authentication
- free_tier
- pricing
- limits
- latency
- quality
- regions
- commercial_use
- health
- adapter

Бесплатность является динамическим состоянием, а не постоянным свойством provider.

## Ключи

API-ключи не зашиваются в исходный код.

Предусматриваются:
- пользовательские API keys;
- OAuth/API authentication;
- безопасное локальное хранение;
- проверка валидности;
- quota tracking;
- отключение/замена ключа.

## Принцип маршрутизации

Оркестратор должен выбирать provider с учётом:

1. типа задачи;
2. требуемого качества;
3. скорости;
4. доступности;
5. оставшейся квоты;
6. стоимости;
7. региона;
8. лицензии/коммерческого использования;
9. пользовательского режима FREE/MY_KEYS/MIXED;
10. выбранной пользователем модели, если политика фиксирована.

## Важное ограничение

Free-tier нельзя считать вечным.

Лимиты, модели, цены, API-доступность и условия использования могут изменяться.

Поэтому каталог должен иметь механизм актуализации и health-check.

## Текущая модель оркестрации

Provider Catalog
       ↓
Auth Manager
   ├── Free account
   ├── User API keys
   └── OAuth/API authentication
       ↓
Provider Health
       ↓
Quota Tracker
       ↓
Capability Router
       ↓
Remote Provider

## Контроль лицензий

Оркестратор обязан учитывать коммерческие ограничения provider.

Например, бесплатный тариф может разрешать тестирование, но запрещать коммерческое использование или требовать атрибуцию.

Такие ограничения должны быть частью metadata provider и учитываться при автоматическом выборе.

## Следующий этап

После завершения каталога providers:

1. реализовать единый Provider Registry;
2. реализовать Provider Adapter interface;
3. подключить реальные remote API;
4. реализовать Auth Manager;
5. реализовать FREE / MY_KEYS / MIXED;
6. реализовать Health + Quota;
7. реализовать fallback;
8. подключить UI;
9. провести реальный end-to-end тест генерации.

## Общий график проекта

- ✅ 1. Базовая архитектура
- ✅ 2. AI Director
- ✅ 3. Reactive Orchestrator
- ✅ 4. Generation / Asset Registry / Render
- 🔄 5. Реальные AI-провайдеры
- ⬜ 6. Полная UI-интеграция
- ⬜ 7. End-to-end тест
- ⬜ 8. Финальный аудит + GitHub
