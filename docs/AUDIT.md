# Аудит WB TRAINER перед миграцией в Telegram Mini App

Дата аудита: 31 июля 2026 года.

## 1. Область аудита

Исходный проект находился в корне репозитория в архиве
`WB-TRAINER-main (1).zip`. Для воспроизводимого дальнейшего развития содержимое
архива распаковано в корень репозитория без изменения исходного Python-кода.
Бинарной базы данных в архиве нет: при первом запуске она создаётся приложением.

Текущая структура:

```text
.
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   ├── database.py
│   ├── handlers.py
│   ├── keyboards.py
│   ├── questions_bank.py
│   └── states.py
├── tests/
│   └── test_questions_bank.py
├── voprosi_wb.txt
├── main.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## 2. Точка запуска и зависимости

- Точка запуска — `main.py`, функция `main()`, запускаемая через
  `asyncio.run(main())`.
- Создаётся `aiogram.Bot`, диспетчер с `MemoryStorage`, подключается единый router,
  и запускается long polling.
- До polling вызывается `init_db()`, которая создаёт и частично обновляет SQLite.
- Docker запускает тот же процесс командой `python main.py`; отдельного API и
  frontend-контейнера сейчас нет.
- Зафиксированы `aiogram 3.22.0`, `aiosqlite 0.21.0` и
  `python-dotenv 1.1.1`.
- FastAPI, SQLAlchemy, Alembic, React, TypeScript, Vite и Telegram Mini Apps SDK
  пока отсутствуют.

## 3. Конфигурация

Текущие переменные: `BOT_TOKEN`, `ADMINS`, `DATABASE`. Список `ADMINS`
преобразуется в Telegram ID и является источником роли super admin. При этом в
коде есть небезопасное значение ID по умолчанию. Нет настроек URL Mini App,
окружения, CORS, срока `initData` и явно отключаемого dev-auth.

## 4. Роли и модель доступа

Поддерживаются три внутренних значения:

- `super_admin` — определяется членством Telegram ID в `ADMINS`;
- `admin` — назначается super admin при привязке владельца ПВЗ;
- `employee` — создаётся при регистрации по invite-коду.

Проверки выполняются непосредственно в обработчиках. Для части операций они
достаточны, но централизованной policy/RBAC-системы нет. Admin получает ПВЗ через
`pvz.owner_id`, хотя `users` также содержит `pvz_id`. Это дублирование источника
истины уже создаёт риск рассинхронизации. Ограничение `pvz.owner_id UNIQUE`
означает, что один admin фактически может владеть не более чем одним ПВЗ, несмотря
на названия функций во множественном числе.

## 5. Регистрация и ПВЗ

1. `/start` пытается создать super admin из Telegram-профиля, если его ID входит
   в `ADMINS`.
2. Существующему пользователю показывается ролевое reply-меню.
3. Новый пользователь вводит invite-код вручную.
4. При валидном коде создаётся employee с `pvz_id`; владельцу ПВЗ отправляется
   уведомление.
5. Super admin создаёт ПВЗ, получает случайный код `WB-XXXXXX`, назначает и
   снимает владельца.

Сейчас отсутствуют invitation-сущность, срок действия, одноразовость, лимиты,
статус приглашения и deep-link payload. Удаление сотрудника и ПВЗ физическое, а
не мягкое. `create_pvz` записывает Telegram ID super admin в `owner_id`, хотя
название поля выглядит как ссылка на внутренний `users.id`; внешний ключ не
задан.

## 6. Текущая схема SQLite

### `pvz`

`id`, `name`, уникальный `invite_code`, уникальный `owner_id`, `created_at`.

### `users`

`id`, уникальный `telegram_id`, `username`, `full_name`, роль с CHECK,
`pvz_id`, `created_at`. Нет фото, блокировки, статуса, last activity, timezone,
XP и streak.

### `questions`

`id`, уникальный `external_id`, `category`, `difficulty`, `type`, уникальный
`question`, JSON-тексты `answers` и `correct_answers`, `explanation`, `weight`,
`created_at`. Таблица создаётся, но TXT в неё не импортируется и тесты читают
файл напрямую. Нет option ID, исходного текста, source/hash, timestamps update,
active/review/auto-generated-флагов.

### `results`

Итог пользователя и ПВЗ: score/percentage, correct/total, duration, JSON ошибок,
category, created_at. Нет серверной попытки и отдельных ответов.

### `broadcasts`

Только агрегат отправки: sender, content type/text, recipients, success, failed,
created_at. Нет отдельных получателей, расписания и классификации ошибок.

### `mandatory_tests`

Creator, один `pvz_id`, title и два JSON-списка пользователей. Обработчик
назначения в текущем коде отсутствует, несмотря на кнопку меню.

### Индексы

Есть индексы users(role/pvz), results(user/pvz), questions(category), а также
автоиндексы UNIQUE. Не хватает большинства индексов, необходимых новой модели
попыток, назначений, аудита и приглашений.

Миграция `_migrate` умеет только добавлять три поля в `results` и `external_id`
в `questions`. Версионирования, транзакционного плана, downgrade и Alembic нет.

## 7. Тестирование и вопросы

Источник — UTF-8 TXT `voprosi_wb.txt`. Он содержит 75 блоков с ID `WB-0001` —
`WB-0075`. Формат неоднороден:

- заголовки `Категория`, `Сложность`, `Тип` часто пропущены, и значения
  наследуются/подставляются parser-ом;
- маркер `Варианты` присутствует только у части блоков, но варианты `A.`–`H.`
  parser также ищет прямо в блоке;
- правильный ответ обозначен как `Правильный ответ`, `Правильные ответы` или
  `Ответ`;
- объяснение есть не в каждом блоке;
- встречаются single, multiple, sequence, situation, practical case и search
  error;
- некоторые блоки содержат правильный ответ текстом либо не подходят для
  кнопочного интерфейса.

Текущий parser принимает 67 из 75 блоков: 45 в категории «Общая работа ПВЗ» и
22 в «Приёмка товара»; 47 имеют тип single, 15 situation, 5 practical case.
Все принятые получают difficulty 1 из-за разреженной разметки. Восемь блоков
отбрасываются без журнала причин или очереди review.

Тест строится случайным перемешиванием и срезом **до** 30 вопросов. Полный банк
достаточен для 30, но категория с 22 вопросами выдаёт только 22, то есть
требование «ровно 30» не обеспечено для категорий.

Варианты перемешиваются согласованно с индексами правильных ответов. Однако
полный набор вопросов и правильных индексов хранится в Telegram FSM
`MemoryStorage`, то есть на стороне процесса бота, а не в БД. Попытка исчезает
при рестарте; параллельное устройство, replay callback, двойное нажатие и
повторное завершение надёжно не защищены. Callback не проверяет владельца
сообщения/попытки и текущий question ID. Результат рассчитывает bot handler и
сохраняет только итог. Ошибки сохраняют текст вопроса и правильные **индексы**, а
не стабильные option ID и не ответ пользователя.

## 8. Существующие функции, которые необходимо сохранить

- `/start`, регистрация по коду и создание super admin из конфигурации;
- ролевые меню и резервный текстовый интерфейс;
- создание/просмотр/удаление ПВЗ, назначение владельца;
- профили и базовая статистика пользователя, ПВЗ и системы;
- список сотрудников с ограничением admin по своему ПВЗ;
- прохождение full/category теста, перемешивание вариантов, обратная связь и
  сохранение результата;
- уведомление владельца о новом сотруднике;
- scoped-рассылка admin и глобальная рассылка super admin с подтверждением;
- TXT как авторитетный источник исходных вопросов;
- Docker-запуск бота и volume для SQLite.

## 9. Выявленные дефекты и риски

### Критические

- Нет Mini App, backend API и проверки Telegram `initData`.
- Нет серверной модели попытки; правильные ответы находятся в состоянии FSM.
- MemoryStorage уничтожает активные тесты при перезапуске.
- Повторный callback может повторно увеличить `correct_count`: флаг `answered`
  устанавливается, но не проверяется.
- Физическое удаление пользователей/ПВЗ противоречит сохранению истории и
  требованиям аудита.
- Нет полноценной системы миграций и проверки миграции на копии БД.

### Высокие

- Wildcard imports, плотные однострочные handlers и смешение UI/business/data
  логики затрудняют безопасное расширение.
- В нескольких обработчиках доступ проверяется через `ADMINS`, а в других через
  роль БД; возможна рассинхронизация.
- Назначение владельца не проверяет существование ПВЗ и конфликт UNIQUE.
- Таблица questions не используется runtime-логикой.
- Нет XP ledger, achievements, streak, leaderboard, assignments workflow,
  audit log, blocks и permissions.
- Логи рассылки через exception могут содержать больше деталей, чем необходимо;
  структурированного redaction нет.

### Средние

- В UI admin называется «Менеджер ПВЗ», а требование задаёт
  «Администратор».
- Кнопки рейтинга и настроек отвечают обещанием будущей реализации; кнопка
  обязательного теста не имеет рабочего handler.
- Варианты Telegram-кнопок обрезаются до 45 символов.
- Нет пагинации; большие списки могут превысить лимит Telegram-сообщения.
- Нет rate limiting, idempotency keys, CORS/config validation и healthcheck.
- Unit discovery из корня не находит тесты без явного указания каталога.

## 10. Безопасная стратегия миграции

1. Сначала зафиксировать текущую схему и написать backup/restore + baseline
   Alembic, не удаляя таблицы и поля.
2. Ввести backend пакет рядом с существующим `app`, подключив его к той же БД.
   Старый bot продолжает работать, пока use cases по одному переносятся в
   сервисы.
3. Нормализовать users/PVZ membership без немедленного удаления `users.pvz_id`
   и `pvz.owner_id`; заполнить новые связи миграцией и некоторое время выполнять
   совместимое чтение.
4. Импортировать TXT идемпотентно в questions/options с source hash и review
   status. Исходный TXT не менять. Неоднозначные восемь и любые автоматически
   дополненные вопросы исключать до review.
5. Реализовать Telegram auth и short-lived backend session, затем `/me` и RBAC с
   обязательным scope ПВЗ.
6. Реализовать DB-backed attempts/answers и только после тестов переключить bot и
   Mini App на общий testing service.
7. Добавить React Mini App поверх реального `/api/v1`, начиная с auth/home/test.
8. Переносить статистику, XP, achievements, rating, assignments, admin и
   broadcasts отдельными миграциями и небольшими коммитами.
9. Сохранять bot fallback до прохождения integration/security tests.

Перед каждой миграцией SQLite: остановить запись, создать timestamped backup,
применить upgrade к копии, проверить `PRAGMA integrity_check` и ключевые counts,
проверить downgrade на отдельной копии и только затем обновлять production.

## 11. План этапов и файлов

### Этап 2 — backend foundation

Создать `backend/app/{api/v1,bot,core,db,models,repositories,schemas,services,utils}`,
`backend/migrations`, `backend/tests`, Alembic-конфигурацию. Изменить конфигурацию,
Docker Compose, entrypoint и зависимости. Старые `app/*` сначала оставить как
compatibility layer.

### Этап 3 — frontend foundation

Создать `frontend` (Vite/React/TypeScript), SDK adapter, API client, auth store,
design tokens/components, employee shell, home/profile/navigation и состояния
ошибок. Изменить Docker build и FastAPI static serving/reverse proxy.

### Этап 4 — secure testing

Создать importer, question/option/attempt/answer models and services, endpoints и
integration tests; затем заменить bot FSM testing на общий backend service.

### Этапы 5–7

Добавить XP/achievements/streak/rating, admin scopes and UI,
assignments/invitations/broadcast/audit, затем production Docker, healthchecks,
backup scripts и полную эксплуатационную документацию.

Точный перечень затрагиваемых файлов уточняется перед каждым этапом после чтения
их актуального состояния. Это снижает риск большого слепого rewrite.

## 12. Решение по результатам аудита

Текущий проект пригоден как рабочий bot fallback и источник legacy-данных, но не
как основа безопасного Mini App без выделения API и серверной модели попыток.
Следующий допустимый шаг — этап 2: конфигурация, async SQLAlchemy/Alembic,
Telegram `initData` verifier, `/api/v1/auth`, `/api/v1/me`, RBAC и совместный
запуск FastAPI + bot. Frontend до завершения этой основы подключать не следует.
