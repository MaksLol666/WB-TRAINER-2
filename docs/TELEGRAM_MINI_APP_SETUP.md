# Как подключить WB TRAINER Mini App к Telegram

> Сейчас в репозитории присутствует только Telegram-бот. Эти шаги следует
> выполнять после появления и публикации frontend + backend из этапов 2–3.
> Одна настройка BotFather не превратит текущий bot-only проект в Mini App.

## Что должно быть опубликовано

1. Публичный **HTTPS** URL frontend, например `https://trainer.example.ru/`.
2. Публичный HTTPS API, например `https://trainer.example.ru/api/v1`.
3. Backend с тем же `BOT_TOKEN`, который серверно проверяет
   `Telegram.WebApp.initData` и не принимает Telegram ID от клиента.
4. Значение `MINI_APP_URL=https://trainer.example.ru/` в production environment.
5. Домен в `CORS_ORIGINS` (если API находится на другом origin).

Нельзя использовать `localhost`, HTTP или URL, доступный только из локальной
сети. Для разработки нужен временный HTTPS tunnel, но URL tunnel нельзя считать
стабильной production-настройкой.

## Настройка через BotFather

1. Откройте официальный `@BotFather` и выполните `/mybots`.
2. Выберите bot WB TRAINER.
3. Откройте **Bot Settings → Menu Button → Configure menu button**.
4. Отправьте публичный HTTPS URL Mini App.
5. Укажите подпись кнопки, например **Открыть WB TRAINER**.
6. При необходимости настройте название/описание приложения в разделе
   **Web Apps**. Названия пунктов BotFather могут немного отличаться между
   версиями интерфейса.

Для production используйте постоянный домен. После смены URL одновременно
обновляйте BotFather и `MINI_APP_URL` на сервере.

## Кнопка из `/start`

Bot должен отправлять inline-кнопку именно с `WebAppInfo`, а не обычную URL-кнопку:

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Открыть WB TRAINER",
                web_app=WebAppInfo(url=settings.mini_app_url),
            )
        ]
    ]
)
```

URL должен приходить из environment. Если `MINI_APP_URL` отсутствует, bot должен
сохранить рабочее текстовое меню, а не отправлять сломанную кнопку.

## Обязательный handshake frontend/backend

1. Mini App вызывает `Telegram.WebApp.ready()` и `expand()`.
2. Frontend читает **неизменённую строку** `Telegram.WebApp.initData`.
3. Строка отправляется на `POST /api/v1/auth/telegram` по HTTPS.
4. Backend проверяет HMAC Telegram, `hash`, `auth_date` и максимальный возраст.
5. Только после успешной проверки backend извлекает `user.id`, создаёт/находит
   пользователя и выдаёт собственную короткоживущую сессию.
6. Все последующие endpoints получают пользователя из этой сессии. `initDataUnsafe`
   разрешено использовать для предварительного UI, но нельзя считать
   авторизацией.

Dev-auth должен быть выключен по умолчанию и обязан аварийно отказываться
включаться при `ENVIRONMENT=production`.

## Проверка после подключения

1. Откройте `/start` в личном чате с bot и нажмите Web App кнопку.
2. Убедитесь, что приложение открывается внутри Telegram, а не во внешнем
   браузере.
3. Проверьте успешный auth существующего пользователя и создание нового.
4. Измените один символ в тестовом `initData` и убедитесь, что API возвращает
   `401`.
5. Проверьте просроченный `auth_date` и доступ admin к чужому ПВЗ — оба должны
   отклоняться.
6. Проверьте Android, iOS и Telegram Desktop, ширину 320 px, safe areas и
   Telegram BackButton.
7. Во время активного теста проверьте closing confirmation и продолжение после
   повторного открытия.

## Частые причины, почему Mini App не открывается

- URL не использует HTTPS или сертификат недействителен;
- frontend недоступен из публичного интернета;
- в BotFather остался старый URL;
- CSP/CORS запрещает frontend или API;
- frontend не подключил Telegram Web App script/SDK;
- Web App кнопку отправляет другой bot, чей token не соответствует verifier;
- backend доверяет `initDataUnsafe` или получает пустой `initData` при открытии
  страницы в обычном браузере;
- Telegram закэшировал старую frontend-сборку — используйте versioned assets и
  корректные cache headers.

## Минимальный production-чеклист владельца

- создать bot и сохранить token только в секретах хостинга;
- привязать постоянный домен и HTTPS;
- задать `BOT_TOKEN`, `DATABASE_URL`, `MINI_APP_URL`, `ENVIRONMENT=production`,
  `CORS_ORIGINS`, `SUPER_ADMIN_IDS`, `TELEGRAM_INIT_DATA_MAX_AGE` и
  `DEV_AUTH_ENABLED=false`;
- выполнить миграции и healthcheck до открытия bot пользователям;
- настроить menu button в BotFather;
- проверить `/start`, auth, роли и резервное копирование БД;
- никогда не публиковать `.env`, token или полное `initData` в логах.
