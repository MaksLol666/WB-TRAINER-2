
# WB TRAINER — Telegram Mini App

WB TRAINER — мобильная система обучения сотрудников ПВЗ. Telegram-бот остаётся
точкой входа и резервным интерфейсом, FastAPI проверяет Telegram `initData` и
рассчитывает тесты на сервере, а React Mini App предоставляет основной интерфейс.

## Что реализовано

- Aiogram 3: `/start`, регистрация по invite-коду, уведомления, рассылки и
  резервные ролевые меню.
- FastAPI `/api/v1`: Telegram auth, профиль/dashboard, попытки, результаты,
  достижения, рейтинг и scoped admin endpoints.
- Серверная попытка ровно на 30 вопросов: порядок хранится в SQLite, клиент
  получает только текущий вопрос, ответ фиксируется один раз, option ID
  проверяется сервером, незавершённую попытку можно продолжить.
- Идемпотентная синхронизация 67 пригодных кнопочных вопросов из
  `voprosi_wb.txt` в нормализованные `questions` и `question_options`.
- Backend XP, уровни, базовые достижения и серия активности.
- React/TypeScript/Vite интерфейс с главной, тестом, результатом, рейтингом,
  достижениями, профилем и scoped-панелью управления.
- Чёрно-фиолетовая мобильная дизайн-система, safe-area, состояния загрузки и
  ошибок, haptics и `prefers-reduced-motion`.
- Один production Docker image со frontend, API и bot polling; healthcheck и
  постоянный volume SQLite.

Подробный аудит legacy-версии находится в [`docs/AUDIT.md`](docs/AUDIT.md).

## Архитектура

```text
Telegram → Aiogram bot ─┐
                       ├→ общая SQLite БД
Mini App → FastAPI API ┘
     ↑ React/Vite static build
```

`app/api.py` содержит versioned HTTP API, `app/services.py` — серверные use cases
тестирования, `app/telegram_auth.py` — проверку Telegram и подписанные сессии.
Legacy bot handlers пока сохранены в `app/handlers.py`.

## Переменные окружения

Скопируйте пример:
=======
# WB TRAINER Telegram Bot v1.1

WB TRAINER — Telegram-бот для обучения, тестирования и контроля сотрудников пунктов выдачи Wildberries.

## Возможности v1.1

- роли `SUPER_ADMIN`, `ADMIN`, `EMPLOYEE`;
- регистрация сотрудников по invite-коду ПВЗ;
- профили пользователей и ПВЗ с показателями;
- тестирование на 30 вопросов из `voprosi_wb.txt`;
- тестовые вопросы только с выбором ответа кнопками;
- одноразовый сценарий теста через FSM с удалением предыдущих сообщений после кнопки «Далее»;
- сохранение результатов, процентов, ошибок и времени прохождения;
- достижения и уровни сотрудников;
- статистика администраторов и супер-администратора;
- списки сотрудников по ПВЗ;
- рассылки с текстом, emoji, фото, видео и документами;
- история рассылок в таблице `broadcasts`;
- Docker/Docker Compose запуск одной командой.

## Настройка


```bash
cp .env.example .env
```


Обязательные production-значения:

- `BOT_TOKEN` — token от BotFather;
- `BOT_ENABLED=true` — запуск Telegram polling (значение `false` допустимо только
  для намеренного API-only режима);
- `SUPER_ADMIN_IDS` — Telegram ID через запятую;
- `DATABASE_URL=sqlite+aiosqlite:///data/wb_trainer.db`;
- `MINI_APP_URL` — публичный HTTPS URL;
- `SESSION_SECRET` — длинная случайная строка;
- `ENVIRONMENT=production`;
- `CORS_ORIGINS` — разрешённые HTTPS origins;
- `DEV_AUTH_ENABLED=false`.

`DEV_AUTH_ENABLED=true` допустим только локально. Приложение откажется стартовать
с dev-auth в production.

## Запуск через Docker

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
```

При старте создаются совместимые таблицы, синхронизируются вопросы, запускаются
FastAPI и polling бота. Mini App доступен на порту 8000.

Если `BOT_ENABLED=true`, сервис теперь завершает запуск с понятной ошибкой при
отсутствующем `BOT_TOKEN` (а в production также `MINI_APP_URL`). Это исключает
ложно успешный деплой, в котором API работает, но бот не получает обновления.

## Локальная разработка

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Frontend с proxy на backend:

```bash
cd frontend
npm install
npm run dev
```

Обычный браузер не предоставляет `initData`. Локальный dev-auth endpoint доступен
только при `DEV_AUTH_ENABLED=true`; production никогда не должен включать его.

## Подключение к Telegram

1. Опубликуйте Docker-сервис на постоянном HTTPS-домене.
2. Укажите этот URL в `MINI_APP_URL` и `CORS_ORIGINS`.
3. В `@BotFather`: `/mybots` → bot → **Bot Settings → Menu Button** → передайте
   тот же HTTPS URL и название «Открыть WB TRAINER».
4. Перезапустите сервис. `/start` отправит кнопку `WebAppInfo`; menu button также
   откроет приложение.
5. Проверяйте приложение именно внутри Telegram. Backend принимает Telegram ID
   только из проверенного `initData`.

При каждом запуске bot самостоятельно устанавливает команды `/start`, `/menu` и
постоянную кнопку меню через Telegram Bot API. Если `MINI_APP_URL` не задан,
вместо сломанной Web App кнопки остаётся стандартное меню команд.

Расширенная инструкция и troubleshooting:
[`docs/TELEGRAM_MINI_APP_SETUP.md`](docs/TELEGRAM_MINI_APP_SETUP.md).

## Первый ПВЗ и сотрудник

1. Добавьте свой Telegram ID в `SUPER_ADMIN_IDS` и отправьте `/start`.
2. В резервном меню выберите «Создать ПВЗ».
3. Передайте сотруднику созданный invite-код.
4. Сотрудник отправляет `/start`, вводит код и затем открывает Mini App.

Legacy-модель пока назначает одного admin одному ПВЗ. Нормализация
`pvz_members/admin_permissions` остаётся следующим совместимым migration этапом.

## Вопросы

Исходник — `voprosi_wb.txt` в UTF-8. При старте пригодные вопросы обновляются по
`external_id`, поэтому повторная синхронизация не создаёт дубликаты. Открытые и
sequence-вопросы не включаются в single-choice тест до появления отдельного UI и
административной проверки.

## Проверки

```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py' -v
python -m compileall -q app main.py
cd frontend && npm run typecheck && npm run build
docker compose config
```

## Резервное копирование SQLite

Остановите запись перед файловой копией:

```bash
docker compose stop wb-trainer-bot
cp data/wb_trainer.db "data/wb_trainer-$(date -u +%Y%m%dT%H%M%SZ).db"
docker compose start wb-trainer-bot
```

Для восстановления остановите сервис, сохраните текущую БД под другим именем,
скопируйте backup в `data/wb_trainer.db`, запустите сервис и проверьте `/health`.
Не публикуйте `.env`, database backup или полное Telegram `initData`.

## Текущие границы

Реализован интегрированный production foundation и основной безопасный тестовый
путь. Следующими небольшими миграциями должны быть добавлены полноценные
назначения тестов, редактор вопросов, scheduled broadcast recipients, мягкое
удаление, расширенный audit UI и Alembic baseline для уже существующих БД.
